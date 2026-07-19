# iaglobal/utils/atomic_io.py
"""Escrita atômica de JSON em disco + ciclo read-modify-write seguro para
estado compartilhado entre múltiplos agentes, dentro do mesmo processo e
entre processos diferentes.

Duas camadas de proteção:
  1. torn write   -> atomic_write_json() (tempfile + fsync + os.replace)
  2. lost update  -> AtomicJSONStore.mutate() / mutate_sync()
     asyncio.Lock  -> serializa coroutines do mesmo processo
     fcntl.flock   -> serializa processos diferentes (mesmo padrão de _paths.py)

Uso (async — relê disco a cada op):
    store = AtomicJSONStore(Path("data.json"), default=[])
    novo = await store.mutate(lambda data: data + [entry])

Uso (sync — estado residente, já tem threading.Lock):
    with self._lock:
        novo = self._store.mutate_sync(lambda data: {**data, "k": "v"})
        self._data = novo
"""

import asyncio
import copy
import fcntl
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Camada 1 — torn write
# ---------------------------------------------------------------------------

def atomic_write_json(path: Path, data: Any, indent: int = 2) -> None:
    """Escreve *data* como JSON em *path* com garantia atômica.

    tempfile no MESMO diretório (mesmo filesystem, os.replace atômico) +
    fsync + os.replace. Se o processo morrer durante a escrita, o arquivo
    original permanece intacto — a temp é perdida, o destino não corrompe.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp", prefix=f".{path.name}.", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


async def async_atomic_write_json(path: Path, data: Any, indent: int = 2) -> None:
    """Versão async de atomic_write_json (via asyncio.to_thread)."""
    await asyncio.to_thread(atomic_write_json, path, data, indent)


# ---------------------------------------------------------------------------
# Camada 2 — lost update (read-modify-write seguro)
# ---------------------------------------------------------------------------

class AtomicJSONStore:
    """
    Ciclo read-modify-write seguro para JSON compartilhado entre agentes,
    dentro do mesmo processo e entre processos diferentes.

    asyncio.Lock serializa coroutines do mesmo processo antes de entrar no
    fcntl.flock, evitando que múltiplas threads do to_thread pool fiquem
    bloqueadas no mesmo flock simultaneamente.
    """

    def __init__(self, path: Path, default: Any = None):
        self.path = path
        self._default = default if default is not None else {}
        self._proc_lock = asyncio.Lock()

    async def mutate(self, fn: Callable[[Any], Any]) -> Any:
        """Versão async de mutate_sync (para quem relê disco a cada op)."""
        async with self._proc_lock:
            return await asyncio.to_thread(self.mutate_sync, fn)

    async def read(self) -> Any:
        """Leitura fora do ciclo de mutação. Não bloqueia outros processos,
        mas pode ver estado stale se outro processo estiver no meio de um
        mutate() -- use mutate() se a leitura precisa ser consistente com
        uma escrita subsequente."""
        return await asyncio.to_thread(self._read_sync)

    def read_sync(self) -> Any:
        """Versão síncrona de read() -- para uso em __init__ ou métodos
        síncronos que já rodam fora do event loop (ex.: chamados via
        run_in_executor)."""
        return self._read_sync()

    def _lock_path(self) -> Path:
        return self.path.parent / f"{self.path.name}.lock"

    def mutate_sync(self, fn: Callable[[Any], Any]) -> Any:
        """Versão síncrona do ciclo read-modify-write, com fcntl.flock
        (inter-processo) mas SEM o asyncio.Lock deste objeto.

        Uso: classes com estado residente em memória e seu PRÓPRIO
        threading.Lock (same_engine.py, meta_evolver.py, homocysteine_pool.py,
        glutathione_pool.py). Chame de DENTRO do lock intra-processo já
        existente da classe -- este método só cuida da parte inter-processo
        (fcntl.flock) e da releitura fresca do disco. O chamador é
        responsável por atualizar seu próprio atributo residente com o
        retorno:

            with self._lock:
                self._data = self._store.mutate_sync(lambda fresh: fresh + [entry])
                return self._data

        Se chamado a partir de código async SEM estar dentro de um
        asyncio.to_thread, isso bloqueia o event loop pelo tempo do
        fcntl.flock.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._lock_path(), "w") as lockf:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
            try:
                current = self.read_sync()
                new_data = fn(current)
                atomic_write_json(self.path, new_data)
                return new_data
            finally:
                fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)

    def _read_sync(self) -> Any:
        if not self.path.exists():
            return copy.deepcopy(self._default)
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("[AtomicJSONStore] falha lendo %s, usando default: %s",
                           self.path, e)
            return self._default
