# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""MultiCoderAgent — Gera backend, frontend e database em paralelo delegando para CoderAgent."""

"""MultiCoderAgent — Gera backend, frontend e database em paralelo delegando para CoderAgent."""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from iaglobal.agents.coder_agent import CoderAgent
from iaglobal.memory.memory_error import record_error

logger = logging.getLogger("iaglobal.agents.multi_coder_agent")

# 1. Contextos enriquecidos (Instruções claras para o LLM, sem espaços fantasmas)
_PARTS: List[Tuple[str, str, str]] = [
    ("backend", "Backend", "Focus on backend logic, API endpoints, and business rules."),
    ("frontend", "Frontend", "Focus on user interface, components, and client-side state."),
    ("database", "Database", "Focus on database schema, models, migrations, and queries."),
]

# Timeout padrão para cada geração (evita que a pipeline trave se o LLM demorar)
_DEFAULT_TIMEOUT = 120.0 

@dataclass
class MultiCoderResult:
    status: str
    parts: Dict[str, str] = field(default_factory=dict)
    consolidated_code: str = ""  # Novo: Output unido para fácil consumo downstream
    total_chars: int = 0
    failures: int = 0
    errors: Dict[str, str] = field(default_factory=dict)  # Novo: Rastreia o motivo da falha

class MultiCoderAgent:
    def __init__(self, coder_agent: Optional[CoderAgent] = None):
        # 2. Injeção de Dependência: Instancia o CoderAgent UMA VEZ só.
        self._coder_agent = coder_agent or CoderAgent()
        # 3. Semáforo ajustado: Como são exatamente 3 partes, não faz sentido semáforo de 6.
        self._sem = asyncio.Semaphore(3) 

    async def generate(self, prompt: str, timeout: float = _DEFAULT_TIMEOUT) -> MultiCoderResult:
        tasks = []
        for key, label, context in _PARTS:
            tasks.append(self._generate_part(key, label, context, prompt, timeout))

        # Executa as 3 partes em paralelo
        results = await asyncio.gather(*tasks)

        parts = {}
        errors = {}
        all_code: List[str] = []
        failures = 0
        
        for key, code, error_msg in results:
            parts[key] = code
            if code:
                all_code.append(f"# === {key.upper()} ===\n{code}")
            else:
                failures += 1
                if error_msg:
                    errors[key] = error_msg

        consolidated_code = "\n\n".join(all_code) if all_code else ""
        
        if failures == len(_PARTS):
            record_error("multi_coder", "Todas as partes falharam", {"prompt_len": len(prompt), "errors": errors})

        if failures == 0:
            status = "full"
        elif failures < len(_PARTS):
            status = "partial"
        else:
            status = "failed"

        logger.info(
            "[MULTI_CODER] status=%s | successes=%d/%d | total_chars=%d",
            status, len(_PARTS) - failures, len(_PARTS), len(consolidated_code)
        )

        return MultiCoderResult(
            status=status,
            parts=parts,
            consolidated_code=consolidated_code,
            total_chars=len(consolidated_code),
            failures=failures,
            errors=errors,
        )

    async def _generate_part(
        self, part_key: str, part_label: str, context: str, prompt: str, timeout: float
    ) -> Tuple[str, str, Optional[str]]:
        async with self._sem:
            try:
                # 4. Timeout: Garante que a pipeline não trave indefinidamente
                artifact = await asyncio.wait_for(
                    self._coder_agent.generate(task=prompt, contexto=context),
                    timeout=timeout
                )
                
                # Fallback caso o artifact não tenha a propriedade .code
                code = artifact.code if hasattr(artifact, 'code') else str(artifact)
                
                if code and len(code.strip()) > 30:
                    logger.info("%s OK: %d chars", part_label, len(code))
                    return (part_key, code, None)
                
                logger.debug("%s vazio ou muito curto", part_label)
                return (part_key, "", f"{part_label} returned empty or too short code.")
                
            except asyncio.TimeoutError:
                msg = f"{part_label} timed out after {timeout}s"
                logger.warning(msg)
                return (part_key, "", msg)
            except Exception as e:
                msg = f"{part_label} failed: {str(e)}"
                logger.warning(msg, exc_info=True)
                return (part_key, "", msg)
