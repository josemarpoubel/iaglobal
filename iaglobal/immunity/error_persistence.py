# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""ErrorPersistence — materializa erros de runtime em store estruturada.

Motivo (Lei 1 — a célula sente seu próprio estado): o sistema analisa a própria
saúde lendo `errors.json` (`FailureAnalysisAgent`) e a pasta `error/`. Se estes
permanecerem vazios enquanto o `app.log` registra dezenas de erros (imports
quebrados, parasitas MHC, exceções), a métrica '0 erros' é FALSA e o organismo
evolui contra uma autoimagem ilusória.

Este módulo:
  - expõe `record_runtime_error` / `record_learning_error` (API explícita);
  - instala um `logging.Handler` no logger 'iaglobal' que persiste todo registro
    ERROR em `errors.json` + `error/<ts>_<componente>.md` (idempotente);
  - tolera falhas de I/O (nunca quebra o logging nem a geração).
"""
import json
import logging
import os
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from iaglobal._paths import ERROR_LOG, ERROR_DIR

logger = logging.getLogger(__name__)

MAX_RUNTIME_ERRORS = int(os.environ.get("IAGLOBAL_MAX_RUNTIME_ERRORS", "200"))
_lock = threading.Lock()
_installed = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load() -> dict:
    try:
        if ERROR_LOG.exists():
            with open(ERROR_LOG) as f:
                return json.load(f)
    except Exception:
        pass
    return {"updated_at": "", "learning_errors": [], "runtime_errors": []}


def _save(data: dict) -> None:
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ERROR_LOG, "w") as f:
        json.dump(data, f, indent=2)


def record_runtime_error(component: str, message: str, tb: str = "") -> None:
    """Persiste um erro de runtime na store estruturada + pasta error/."""
    try:
        ERROR_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": _now_iso(),
            "component": component,
            "source": component,
            "message": (message or "")[:2000],
            "traceback": (tb or "")[:8000],
        }
        # 1. Arquivo legível por erro (subconsciente de falhas)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in component)[-40:]
        fname = ERROR_DIR / f"{int(time.time() * 1000)}_{safe}.md"
        try:
            fname.write_text(
                f"# Erro de Runtime\n\n- **Componente**: {component}\n"
                f"- **Time**: {entry['timestamp']}\n\n"
                f"## Mensagem\n```\n{message}\n```\n\n"
                f"## Traceback\n```\n{tb}\n```\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        # 2. Store estruturada (lida por FailureAnalysisAgent)
        with _lock:
            data = _load()
            data.setdefault("runtime_errors", []).append(entry)
            data["runtime_errors"] = data["runtime_errors"][-MAX_RUNTIME_ERRORS:]
            data["updated_at"] = _now_iso()
            _save(data)
    except Exception as e:
        logger.debug("[ERROR_PERSISTENCE] falha ao persistir erro: %s", e)


def record_learning_error(component: str, message: str) -> None:
    """Persiste uma falha de aprendizado (evolução/reflexão)."""
    try:
        with _lock:
            data = _load()
            data.setdefault("learning_errors", []).append({
                "timestamp": _now_iso(),
                "component": component,
                "message": (message or "")[:2000],
            })
            data["updated_at"] = _now_iso()
            _save(data)
    except Exception as e:
        logger.debug("[ERROR_PERSISTENCE] falha ao persistir learning error: %s", e)


class ErrorPersistenceHandler(logging.Handler):
    """Captura registros ERROR do logger 'iaglobal' para a store estruturada.

    Evita recursão: ignora registros originados deste próprio módulo.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.name.startswith("iaglobal.immunity.error_persistence"):
                return
            tb = ""
            if record.exc_info:
                tb = "".join(traceback.format_exception(*record.exc_info))
            record_runtime_error(
                component=record.name,
                message=record.getMessage(),
                tb=tb,
            )
        except Exception:
            pass  # nunca quebrar o logging por causa da persistência


def install() -> None:
    """Instala o handler no logger raiz 'iaglobal' (idempotente)."""
    global _installed
    if _installed:
        return
    root = logging.getLogger("iaglobal")
    for h in root.handlers:
        if isinstance(h, ErrorPersistenceHandler):
            _installed = True
            return
    handler = ErrorPersistenceHandler()
    handler.setLevel(logging.ERROR)
    root.addHandler(handler)
    _installed = True
