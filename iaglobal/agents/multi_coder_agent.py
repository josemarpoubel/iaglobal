"""MultiCoderAgent — Gera backend, frontend e database em paralelo com race multi-modelo."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from iaglobal.memory.memory_error import record_error
from iaglobal.providers.provider_router import async_route_generate

logger = logging.getLogger("iaglobal.agents.multi_coder_agent")

_PARTS: List[Tuple[str, str, str]] = [
    ("backend", "backend", "Gere APENAS o codigo do BACKEND (API, rotas, servidor)"),
    ("frontend", "frontend", "Gere APENAS o codigo do FRONTEND (interface, componentes)"),
    ("database", "database", "Gere APENAS o codigo do BANCO DE DADOS (models, migracoes, schema)"),
]


@dataclass
class MultiCoderResult:
    status: str
    parts: Dict[str, str] = field(default_factory=dict)
    total_chars: int = 0
    failures: int = 0


class MultiCoderAgent:
    def __init__(self):
        self._sem = asyncio.Semaphore(6)

    async def generate(self, prompt: str) -> MultiCoderResult:
        tasks = []
        for key, label, instruction in _PARTS:
            tasks.append(self._generate_part(key, label, instruction, prompt))

        results = await asyncio.gather(*tasks)

        parts = {}
        all_code: List[str] = []
        failures = 0
        for key, code in results:
            parts[key] = code
            if code:
                all_code.append(f"# === {key.upper()} ===\n{code}")
            else:
                failures += 1

        multi_output = "\n\n".join(all_code) if all_code else ""
        if failures == len(_PARTS):
            record_error("multi_coder", "Todas as partes falharam", {"prompt_len": len(prompt)})

        if failures == 0:
            status = "full"
        elif failures < len(_PARTS):
            status = "partial"
        else:
            status = "failed"

        return MultiCoderResult(
            status=status,
            parts=parts,
            total_chars=len(multi_output),
            failures=failures,
        )

    async def _generate_part(self, part_key: str, part_label: str, instruction: str, prompt: str) -> Tuple[str, str]:
        system = "Voce eh um engenheiro de software especialista."
        full_prompt = f"{system}\n\n{prompt}\n\n{instruction}\n\nGere APENAS codigo, sem explicacoes."
        async with self._sem:
            try:
                code = await async_route_generate(model="auto", prompt=full_prompt, task_type="coding")
                if code and len(code) > 30:
                    logger.info("%s OK: %d chars", part_label, len(code))
                    return (part_key, code)
                logger.debug("%s vazio", part_label)
                return (part_key, "")
            except Exception as e:
                logger.warning("%s falhou: %s", part_label, e)
                return (part_key, "")
