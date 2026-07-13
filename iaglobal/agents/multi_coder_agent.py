# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""MultiCoderAgent — Orquestrador que delega para agentes especializados e registra métricas no Bandit."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from iaglobal.agents.coder_agent import CoderAgent
from iaglobal.agents.agent_base import AgentBase
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.agents.multi_coder_agent")

# 1. Contextos enriquecidos (Instruções claras para o LLM, sem espaços fantasmas)
_PARTS: List[Tuple[str, str, str]] = [
    (
        "backend",
        "Backend",
        "Focus on backend logic, API endpoints, and business rules.",
    ),
    (
        "frontend",
        "Frontend",
        "Focus on user interface, components, and client-side state.",
    ),
    (
        "database",
        "Database",
        "Focus on database schema, models, migrations, and queries.",
    ),
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
    errors: Dict[str, str] = field(
        default_factory=dict
    )  # Novo: Rastreia o motivo da falha
    models_used: Dict[str, str] = field(
        default_factory=dict
    )  # Novo: Qual modelo gerou cada parte


class MultiCoderAgent(AgentBase):
    """
    MultiCoderAgent — Orquestrador de geração de código.

    Delega para agentes especializados (backend, frontend, database) e
    registra métricas detalhadas no CreditAssignmentEngine para o Bandit aprender.
    """

    def __init__(self, coder_agent: Optional[CoderAgent] = None):
        # Inicializa AgentBase com nome único
        super().__init__(agent_name="multi_coder")

        # 2. Injeção de Dependência: Instancia o CoderAgent UMA VEZ só.
        self._coder_agent = coder_agent or CoderAgent()
        # 3. Semáforo ajustado: Como são exatamente 3 partes, não faz sentido semáforo de 6.
        self._sem = asyncio.Semaphore(3)

    async def generate(
        self, prompt: str, timeout: float = _DEFAULT_TIMEOUT
    ) -> MultiCoderResult:
        """
        Gera código para backend, frontend e database em paralelo.

        Registra métricas de cada parte no CreditAssignmentEngine para o Bandit aprender.
        """
        tasks = []
        for key, label, context in _PARTS:
            tasks.append(self._generate_part(key, label, context, prompt, timeout))

        # Executa as 3 partes em paralelo
        results = await asyncio.gather(*tasks)

        parts = {}
        errors = {}
        models_used = {}
        all_code: List[str] = []
        failures = 0

        for key, code, error_msg, model_used in results:
            parts[key] = code
            models_used[key] = model_used
            if code:
                all_code.append(f"# === {key.upper()} ===\n{code}")
            else:
                failures += 1
                if error_msg:
                    errors[key] = error_msg

        consolidated_code = "\n\n".join(all_code) if all_code else ""

        # Registra métrica consolidada
        if consolidated_code:
            self._register_custom_metric(
                model="multi_coder_orchestrator",
                task_type="code_generation_full",
                success=(failures == 0),
                latency=0,  # Já registrado em cada parte
                extra_data={
                    "total_chars": len(consolidated_code),
                    "parts_success": len(_PARTS) - failures,
                    "parts_total": len(_PARTS),
                    "models_used": models_used,
                },
            )

        if failures == 0:
            status = "full"
        elif failures < len(_PARTS):
            status = "partial"
        else:
            status = "failed"

        logger.info(
            "[MULTI_CODER] status=%s | successes=%d/%d | total_chars=%d",
            status,
            len(_PARTS) - failures,
            len(_PARTS),
            len(consolidated_code),
        )

        return MultiCoderResult(
            status=status,
            parts=parts,
            consolidated_code=consolidated_code,
            total_chars=len(consolidated_code),
            failures=failures,
            errors=errors,
            models_used=models_used,
        )

    async def _generate_part(
        self, part_key: str, part_label: str, context: str, prompt: str, timeout: float
    ) -> Tuple[str, str, Optional[str], str]:
        """
        Gera uma parte do código e registra métricas no Bandit.

        Returns:
            Tuple de (part_key, code, error_msg, model_used)
        """
        async with self._sem:
            start_time = time.time()
            model_used = "unknown"

            try:
                # 4. Timeout: Garante que a pipeline não trave indefinidamente
                artifact = await asyncio.wait_for(
                    self._coder_agent.generate(task=prompt, contexto=context),
                    timeout=timeout,
                )

                # Fallback caso o artifact não tenha a propriedade .code
                code = artifact.code if hasattr(artifact, "code") else str(artifact)

                # Registra qual modelo foi usado (se disponível no artifact)
                model_used = getattr(artifact, "model_used", "coder_agent_default")

                if code and len(code.strip()) > 30:
                    logger.info(
                        "%s OK: %d chars (model=%s)", part_label, len(code), model_used
                    )

                    # Registra métrica de sucesso no CreditAssignmentEngine
                    self._register_custom_metric(
                        model=model_used,
                        task_type=f"code_{part_key}",
                        success=True,
                        latency=time.time() - start_time,
                        extra_data={
                            "part": part_key,
                            "chars": len(code),
                            "quality": "full" if len(code) > 500 else "partial",
                        },
                    )

                    return (part_key, code, None, model_used)

                logger.debug(
                    "%s vazio ou muito curto (model=%s)", part_label, model_used
                )
                return (
                    part_key,
                    "",
                    f"{part_label} returned empty or too short code.",
                    model_used,
                )

            except asyncio.TimeoutError:
                msg = f"{part_label} timed out after {timeout}s"
                logger.warning(msg)

                # Registra métrica de timeout
                self._register_custom_metric(
                    model=model_used,
                    task_type=f"code_{part_key}",
                    success=False,
                    latency=timeout,
                    extra_data={"error": "timeout", "part": part_key},
                )

                return (part_key, "", msg, model_used)

            except Exception as e:
                msg = f"{part_label} failed: {str(e)}"
                logger.warning(msg, exc_info=True)

                # Registra métrica de falha
                self._register_custom_metric(
                    model=model_used,
                    task_type=f"code_{part_key}",
                    success=False,
                    latency=time.time() - start_time,
                    extra_data={"error": str(e), "part": part_key},
                )

                return (part_key, "", msg, model_used)
