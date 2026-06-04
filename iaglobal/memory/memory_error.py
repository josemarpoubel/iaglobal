# memory_error.py

import json
import threading

from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

from iaglobal import _paths


_lock = threading.Lock()

# ==========================================================
# CORE
# ==========================================================

def _get_error_file() -> Path:
    """Resolve o caminho do arquivo de erros dinamicamente."""
    return Path(_paths.ERROR_LOG)

def _load_db() -> Dict[str, Any]:
    """
    Estrutura única do banco de erros:

    {
      "updated_at": "...",
      "learning_errors": [],
      "runtime_errors": []
    }
    """

    if not _get_error_file().exists():
        return {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "learning_errors": [],
            "runtime_errors": []
        }

    try:
        with open(
            _get_error_file(),
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("Formato inválido.")

        data.setdefault("updated_at", "")
        data.setdefault("learning_errors", [])
        data.setdefault("runtime_errors", [])

        return data

    except Exception:
        return {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "learning_errors": [],
            "runtime_errors": []
        }


def _save_db(data: Dict[str, Any]) -> None:

    _get_error_file().parent.mkdir(
        parents=True,
        exist_ok=True
    )

    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    with open(
        _get_error_file(),
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


# ==========================================================
# LEARNING ERRORS
# ==========================================================

def load_errors() -> List[Dict[str, Any]]:
    return _load_db()["learning_errors"]


def save_errors(
    errors: List[Dict[str, Any]]
) -> None:

    with _lock:
        db = _load_db()
        db["learning_errors"] = errors
        _save_db(db)


def store_error(
    prompt: str,
    response: str,
    critique: str,
    corrected: str,
    error_type: str = "RuntimeError"
) -> None:
    """
    Registra erros usados para aprendizado e prevenção
    de anti-padrões futuros.
    """

    with _lock:

        db = _load_db()

        payload = {
            "id": datetime.now(timezone.utc).strftime(
                "%Y%m%d%H%M%S%f"
            ),
            "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "error_type": error_type,
            "prompt": prompt,
            "response_errada": response,
            "critica_sandbox": critique,
            "codigo_corrigido": corrected
        }

        db["learning_errors"].append(payload)

        # mantém apenas os últimos 1000
        db["learning_errors"] = (
            db["learning_errors"][-1000:]
        )

        _save_db(db)


def query_relevant_errors(
    current_prompt: str,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Busca erros anteriores relevantes ao prompt atual.
    """

    db = load_errors()

    if not db:
        return []

    ignorar = {
        "como",
        "fazer",
        "criar",
        "usando",
        "python",
        "script",
        "erro",
        "falha"
    }

    keywords = {
        word.strip(",.()\"'")
        for word in current_prompt.lower().split()
        if len(word) > 4 and word not in ignorar
    }

    if not keywords:
        return db[-limit:]

    scored_entries = []

    for entry in db:

        contexto = (
            f"{entry.get('prompt', '')} "
            f"{entry.get('critica_sandbox', '')}"
        ).lower()

        score = sum(
            1.5
            if word in entry.get(
                "critica_sandbox",
                ""
            ).lower()
            else 1.0
            for word in keywords
            if word in contexto
        )

        if score > 0:
            scored_entries.append(
                (score, entry)
            )

    scored_entries.sort(
        key=lambda x: (
            x[0],
            x[1].get("time", "")
        ),
        reverse=True
    )

    return [
        item[1]
        for item in scored_entries[:limit]
    ]


def format_errors_for_prompt(
    relevant_errors: List[Dict[str, Any]]
) -> str:

    if not relevant_errors:
        return ""

    buffer = [
        "\n=== HISTÓRICO DE ERROS EVITADOS ==="
    ]

    for idx, err in enumerate(
        relevant_errors,
        start=1
    ):
        buffer.append(
            f"Caso #{idx} [{err['error_type']}]:\n"
            f"  - Prompt: {err['prompt']}\n"
            f"  - Código Incorreto: "
            f"{err['response_errada'].strip()}\n"
            f"  - Motivo: "
            f"{err['critica_sandbox'].strip()}\n"
            f"  - Correção: "
            f"{err['codigo_corrigido'].strip()}\n"
            f"--------------------------------------------------"
        )

    return "\n".join(buffer) + "\n"


# ==========================================================
# RUNTIME / SYSTEM LOGGING
# ==========================================================

def record_error(
    component: str,
    message: str,
    details: dict | None = None,
    execution_id: str | None = None,
    severity: str = "ERROR"
) -> None:

    with _lock:

        db = _load_db()

        db["runtime_errors"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "severity": severity,
            "execution_id": execution_id,
            "message": message,
            "details": details or {}
        })

        # mantém últimos 500 logs operacionais
        db["runtime_errors"] = (
            db["runtime_errors"][-500:]
        )

        _save_db(db)
