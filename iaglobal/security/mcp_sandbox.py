# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/security/mcp_sandbox.py

"""
MCPSandbox — sandbox de tools MCP: whitelist, rate limit, audit trail.
"""

import asyncio
import aiofiles  # Recomendado instalar: pip install aiofiles
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from iaglobal._paths import PROJECT_ROOT
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.security.mcp_sandbox")

AUDIT_PATH = Path(PROJECT_ROOT) / "iaglobal" / "memory" / "data" / "json" / "audit.json"

ALLOWED_TOOLS = {
    "web_search",
    "web_fetch",
    "read_file",
    "write_file",
    "list_dir",
    "execute_code",
    "metabolic_audit",
    "get_ivm",
}

RATE_LIMITS = {
    "web_search": {"calls_per_minute": 10, "cooldown_seconds": 6},
    "web_fetch": {"calls_per_minute": 15, "cooldown_seconds": 4},
    "execute_code": {"calls_per_minute": 5, "cooldown_seconds": 12},
    "read_file": {"calls_per_minute": 30, "cooldown_seconds": 2},
    "write_file": {"calls_per_minute": 10, "cooldown_seconds": 6},
}


class MCPSandbox:
    def __init__(self):

        self._call_log = defaultdict(list)
        self.lock = asyncio.Lock()  # Adicione um lock para proteger o log

    async def validate_call(self, tool_name: str, arguments: dict) -> bool:
        if tool_name not in ALLOWED_TOOLS:
            logger.warning("Tool bloqueada: %s (não está na whitelist)", tool_name)
            return False
        return True

    async def check_rate_limit(self, tool_name: str, agent_id: str = "unknown") -> bool:
        limits = RATE_LIMITS.get(tool_name)
        if not limits:
            return True

        now = time.time()
        window = 60.0
        key = f"{agent_id}:{tool_name}"
        calls = [t for t in self._call_log[key] if now - t < window]
        self._call_log[key] = calls

        if len(calls) >= limits["calls_per_minute"]:
            logger.warning(
                "Rate limit excedido para %s/%s: %d/min",
                agent_id,
                tool_name,
                len(calls),
            )
            return False

        self._call_log[key].append(now)
        return True

    async def audit_call(
        self,
        tool_name: str,
        arguments: dict,
        result: Any,
        agent_id: str = "unknown",
        allowed: bool = True,
    ):
        audit_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "agent_id": agent_id,
            "tool": tool_name,
            "arguments": arguments,
            "result_summary": str(result)[:200] if result else "",
            "sandbox_decision": "allowed" if allowed else "blocked",
        }
        await self._append_audit(audit_entry)
        logger.debug(
            "Audit MCP: %s/%s → %s",
            agent_id,
            tool_name,
            audit_entry["sandbox_decision"],
        )

    async def _append_audit(self, entry: dict):
        async with self.lock:  # Bloqueia a escrita para evitar colisões
            try:
                # Usa leitura assíncrona se disponível ou garanta atomicidade
                if AUDIT_PATH.exists():
                    async with aiofiles.open(
                        AUDIT_PATH, mode="r", encoding="utf-8"
                    ) as f:
                        content = await f.read()
                        data = json.loads(content)
                else:
                    data = {"audits": []}

                data["audits"].append(entry)

                # Truncate seguro
                if len(data["audits"]) > 1000:
                    data["audits"] = data["audits"][-1000:]

                async with aiofiles.open(AUDIT_PATH, mode="w", encoding="utf-8") as f:
                    await f.write(json.dumps(data, indent=2))
            except Exception as e:
                logger.error("Falha ao registar auditoria: %s", e)
