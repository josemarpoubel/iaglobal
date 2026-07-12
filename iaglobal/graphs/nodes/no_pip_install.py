# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Pip Install Node — Instala pacotes Python de forma controlada e segura.

Agentes NÃO chamam subprocess diretamente. Usam este nó DAG que:
1. Valida o pacote contra a whitelist de segurança
2. Executa pip install em thread pool (não bloqueia o event loop)
3. Retorna resultado estruturado para o pipeline
"""
import asyncio
import logging
import time
from typing import Dict, Any

from iaglobal.utils.controlled_subprocess import pip_install, pip_list

logger = logging.getLogger(__name__)


async def run_pip_install(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Instala pacote Python via pip de forma controlada.

    Contexto esperado (ctx["input"]):
        package: str — nome do pacote (ex: "requests", "pandas==2.0")
        timeout: int — timeout em segundos (default 60)
    """
    start_time = time.time()
    resolved_model = "pip_install_controlled"

    inp = ctx.get("input", {})
    package = inp.get("package", "") if isinstance(inp, dict) else ""
    if not package:
        package = ctx.get("package", "")

    if not package:
        return {
            "output": "Nenhum pacote especificado",
            "success": False,
            "error": "package parameter is required",
            "execution_metrics": {
                "model": resolved_model, "success": False,
                "latency": (time.time() - start_time) * 1000, "cost": 0.0,
            },
        }

    timeout = float(ctx.get("timeout", 60))

    try:
        proc = await asyncio.wait_for(
            pip_install(package, timeout=timeout),
            timeout=timeout + 10,
        )

        latency_ms = (time.time() - start_time) * 1000
        success = proc.returncode == 0

        result = {
            "output": proc.stdout or "" if success else (proc.stderr or ""),
            "success": success,
            "package": package,
            "returncode": proc.returncode,
            "execution_metrics": {
                "model": resolved_model, "success": success,
                "latency": latency_ms, "cost": 0.0,
            },
        }

        if success:
            logger.info("[PIP] Pacote instalado: %s (%.0fms)", package, latency_ms)
        else:
            logger.warning("[PIP] Falha ao instalar %s: %s", package, (proc.stderr or "")[:200])
            result["error"] = (proc.stderr or "")[:500]

        return result

    except asyncio.TimeoutError:
        latency_ms = (time.time() - start_time) * 1000
        logger.warning("[PIP] Timeout ao instalar %s", package)
        return {
            "output": "", "success": False, "package": package,
            "error": f"Timeout ({timeout}s)",
            "execution_metrics": {
                "model": resolved_model, "success": False,
                "latency": latency_ms, "cost": 0.0,
            },
        }


async def run_pip_list(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Lista pacotes instalados."""
    start_time = time.time()
    resolved_model = "pip_list_controlled"

    try:
        proc = await pip_list()
        latency_ms = (time.time() - start_time) * 1000
        return {
            "output": proc.stdout or "",
            "success": proc.returncode == 0,
            "execution_metrics": {
                "model": resolved_model, "success": proc.returncode == 0,
                "latency": latency_ms, "cost": 0.0,
            },
        }
    except Exception as e:
        return {
            "output": "", "success": False, "error": str(e),
            "execution_metrics": {
                "model": resolved_model, "success": False,
                "latency": (time.time() - start_time) * 1000, "cost": 0.0,
            },
        }
