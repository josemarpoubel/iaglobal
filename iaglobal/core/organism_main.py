# iaglobal/core/organism_main.py
"""Entry point para subprocesso de organismo iaglobal isolado.

Lê tarefas JSON-RPC do stdin (linha por linha), executa via Orchestrator,
escreve resultado no stdout.

Uso:
    python -m iaglobal.core.organism_main --id worker-1 --data-root /tmp/org-w1
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from iaglobal.core.orchestrator import Orchestrator

logger = logging.getLogger("iaglobal.organism_main")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="iaglobal organism subprocess")
    parser.add_argument("--id", required=True, help="Organism unique ID")
    parser.add_argument(
        "--data-root", required=True, type=Path, help="Data root directory"
    )
    return parser.parse_args()


async def _handle_request(orchestrator: Orchestrator, request: dict) -> dict:
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    try:
        if method == "run_task":
            task = params.get("task", "")
            if not task:
                raise ValueError("task is required")
            result = await orchestrator.execute({"task": task, **params})
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        elif method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"status": "alive", "organism_id": orchestrator.organism_id},
            }
        elif method == "shutdown":
            asyncio.create_task(orchestrator.shutdown())
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"status": "shutting_down"},
            }
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
    except Exception as e:
        logger.exception("[OrganismMain] Erro executando %s", method)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32603, "message": str(e)},
        }


async def _read_stdin():
    """Lê linha do stdin em executor de thread para não travar o event loop."""
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        yield line


async def main_loop():
    args = _parse_args()
    organism_id = args.id
    data_root = args.data_root

    data_root.mkdir(parents=True, exist_ok=True)
    orchestrator = Orchestrator(organism_id=organism_id, data_root=data_root)

    logger.info("[OrganismMain:%s] Ready data_root=%s", organism_id, data_root)

    async for line in _read_stdin():
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = await _handle_request(orchestrator, request)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError as e:
            sys.stdout.write(
                json.dumps(
                    {"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}}
                )
                + "\n"
            )
            sys.stdout.flush()

    await orchestrator.shutdown()
    logger.info("[OrganismMain:%s] Exiting", organism_id)


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    asyncio.run(main_loop())


if __name__ == "__main__":
    main()
