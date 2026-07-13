# iaglobal/core/organism.py
"""Organism — Wrapper que gerencia um subprocesso iaglobal isolado.

Cada instância de Organism representa um organismo computacional vivo,
rodando em seu próprio processo com memória, fila e data_root isolados.

Uso:
    async with Organism("worker-1", data_root=Path("/tmp/org-worker-1")) as org:
        result = await org.run_task("crie uma API Flask")
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("iaglobal.core.organism")


class OrganismError(Exception):
    """Erro do organismo."""


class Organism:
    """Organismo iaglobal isolado em subprocesso.

    Attributes:
        id: Identificador único do organismo.
        data_root: Diretório raiz de dados do organismo.
        process: Subprocesso (None se não iniciado).
    """

    def __init__(self, organism_id: str, data_root: Path, timeout: int = 300):
        self.id = organism_id
        self.data_root = data_root.resolve()
        self.timeout = timeout
        self.process: Optional[asyncio.subprocess.Process] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def start(self):
        """Inicia o subprocesso do organismo."""
        self.data_root.mkdir(parents=True, exist_ok=True)

        proc_env = os.environ.copy()
        proc_env["ORGANISM_DATA_ROOT"] = str(self.data_root)
        proc_env["ORGANISM_ID"] = self.id

        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "iaglobal.core.organism_main",
            "--id",
            self.id,
            "--data-root",
            str(self.data_root),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=proc_env,
        )

        logger.info(
            "[Organism:%s] Spawned PID=%d data_root=%s",
            self.id,
            self.process.pid,
            self.data_root,
        )

    async def ping(self) -> Dict[str, Any]:
        """Verifica se o organismo está vivo."""
        return await self._request("ping", {})

    async def _request(self, method: str, params: dict) -> Dict[str, Any]:
        """Envia um request JSON-RPC e aguarda a resposta."""
        if not self.process or self.process.returncode is not None:
            raise OrganismError(f"Organism {self.id} não está em execução")

        request = {"method": method, "params": params, "id": 1}
        payload = json.dumps(request).encode() + b"\n"
        self.process.stdin.write(payload)
        await self.process.stdin.drain()

        line = await asyncio.wait_for(
            self.process.stdout.readline(), timeout=self.timeout
        )
        if not line:
            stderr = await self.process.stderr.read()
            raise OrganismError(
                f"Organism {self.id} morreu: {stderr.decode(errors='replace')}"
            )

        response = json.loads(line.decode())
        if "error" in response:
            raise OrganismError(f"Organism {self.id} erro: {response['error']}")
        return response.get("result", {})

    async def run_task(self, task: str, **kwargs) -> Dict[str, Any]:
        """Envia uma tarefa e aguarda o resultado."""
        return await self._request("run_task", {"task": task, **kwargs})

    async def stop(self):
        """Finaliza o organismo graciosamente."""
        if self.process and self.process.returncode is None:
            logger.info("[Organism:%s] Terminating PID=%d", self.id, self.process.pid)
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=10)
            except asyncio.TimeoutError:
                logger.warning(
                    "[Organism:%s] Force kill PID=%d", self.id, self.process.pid
                )
                self.process.kill()
                await self.process.wait()

    @property
    def is_alive(self) -> bool:
        return self.process is not None and self.process.returncode is None
