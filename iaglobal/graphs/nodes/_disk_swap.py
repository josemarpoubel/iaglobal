"""Disk swap cache — resultados de busca em disco (evita estourar RAM)."""
import json
import time
import hashlib
from pathlib import Path
from typing import Optional

from iaglobal._paths import SEARCH_SWAP_DIR

_SEARCH_SWAP_DIR = SEARCH_SWAP_DIR
_SEARCH_SWAP_DIR.mkdir(parents=True, exist_ok=True)

_MAX_ENTRIES = 200
_TTL_SECONDS = 3600  # 1h


def _hash_key(source: str, task: str) -> str:
    raw = f"{source}:{task}".encode()
    return hashlib.md5(raw).hexdigest()


def save_search(source: str, task: str, result: str) -> Path:
    key = _hash_key(source, task)
    path = _SEARCH_SWAP_DIR / f"{source}_{key}.json"
    data = {"source": source, "task": task[:200], "result": result, "ts": time.time()}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    _cleanup()
    return path


def load_search(source: str, task: str) -> Optional[str]:
    key = _hash_key(source, task)
    path = _SEARCH_SWAP_DIR / f"{source}_{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - data.get("ts", 0) > _TTL_SECONDS:
            path.unlink(missing_ok=True)
            return None
        return data.get("result")
    except Exception:
        return None


def load_all_for_task(task: str) -> dict:
    """Carrega TODOS os resultados salvos para uma task (qualquer fonte)."""
    results = {}
    if not _SEARCH_SWAP_DIR.exists():
        return results
    for f in _SEARCH_SWAP_DIR.iterdir():
        if f.suffix != ".json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("task", "")[:200] == task[:200]:
                src = data.get("source", "unknown")
                results[src] = data.get("result", "")
        except Exception:
            pass
    return results


def cleanup_task(task: str):
    """Remove todos os resultados de uma task após uso."""
    if not _SEARCH_SWAP_DIR.exists():
        return
    for f in _SEARCH_SWAP_DIR.iterdir():
        if f.suffix != ".json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("task", "")[:200] == task[:200]:
                f.unlink(missing_ok=True)
        except Exception:
            pass


def _cleanup():
    """Remove entradas velhas se passar do limite."""
    files = sorted(_SEARCH_SWAP_DIR.iterdir(), key=lambda f: f.stat().st_mtime)
    if len(files) > _MAX_ENTRIES:
        for f in files[: len(files) - _MAX_ENTRIES]:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass


def swap_status() -> dict:
    """Retorna status do disco de swap."""
    if not _SEARCH_SWAP_DIR.exists():
        return {"files": 0, "size_kb": 0}
    files = list(_SEARCH_SWAP_DIR.iterdir())
    total_kb = sum(f.stat().st_size for f in files if f.is_file()) / 1024
    return {"files": len(files), "size_kb": round(total_kb, 1)}
