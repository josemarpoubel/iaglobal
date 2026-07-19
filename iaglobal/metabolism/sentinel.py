# iaglobal/metabolism/sentinel.py
# Sentinela Paralelo — monitoramento contínuo e non-blocking de artefatos.
# Acopla-se ao Operário via asyncio.Future e dispara intervenções no
# barramento quando detecta violações de requisito.

import asyncio
from typing import Optional

from iaglobal.agents.failure_analysis_agent import FailureAnalysisAgent
from iaglobal.graphs.comms.acetylcholine_bus import (
    AcetylcholineBus, AgentMessage,
)
from iaglobal.providers.provider_router import cognitive_dispatch
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.metabolism.sentinel")


LFM_CONFIRM_PROMPT = """You are a requirements compliance auditor.
Given the user request and the generated code below, check if the code
satisfies the requirements. Output only JSON:
{{"compliant": true/false, "reason": "..."}}

User request:
{request}

Generated code:
{code}
"""


class SentinelOrchestrator:
    """Monitor non-blocking de artefatos em paralelo ao Operário.

    ��� Fluxo:
        1. Recebe um asyncio.Future que o Operário preencherá com o código.
        2. Quando o future resolve, executa check_requirements() (keyword scan).
        3. Se encontrar violações, chama LFM-230M para confirmação semântica.
        4. Se confirmado, publica sentinel_intervention no AcetylcholineBus.
        5. Se o future for cancelado (CancelledError), termina silenciosamente.
    """

    def __init__(self, bus: Optional[AcetylcholineBus] = None) -> None:
        self.bus = bus or AcetylcholineBus()

    async def monitor_task(
        self,
        task_id: str,
        prompt: str,
        code_future: asyncio.Future,
        node_id: str = "sentinel",
    ) -> None:
        """Espreita a conclusão da geração e valida o artefato produzido.

        Args:
            task_id: Identificador único da tarefa no pipeline.
            prompt: Prompt original do usuário (para extrair requisitos).
            code_future: Future que será preenchido pelo Operário com o código.
            node_id: Nome do nó para roteamento cognitivo (default: sentinel).
        """
        try:
            generated_code = await asyncio.wait_for(
                asyncio.shield(code_future), timeout=120.0
            )
        except asyncio.CancelledError:
            logger.debug("[SENTINEL] Task %s cancelada — término gracioso", task_id)
            return
        except asyncio.TimeoutError:
            logger.warning("[SENTINEL] Task %s: timeout aguardando código", task_id)
            return

        if not generated_code or not isinstance(generated_code, str):
            return

        violations = await self._analyze_requirements(prompt, generated_code)
        if not violations:
            return

        await self.bus.publish(
            AgentMessage(
                sender=node_id,
                recipient="pipeline",
                message_type="sentinel_intervention",
                content={
                    "task_id": task_id,
                    "violations": violations,
                    "action": "escalate_to_juiz",
                },
                payload={
                    "source": "SentinelOrchestrator",
                    "severity": "warning",
                },
            )
        )
        logger.info(
            "[SENTINEL] Task %s: %d violação(ões) publicada(s) no barramento",
            task_id, len(violations),
        )

    async def _analyze_requirements(
        self, prompt: str, code: str
    ) -> list[dict]:
        """Híbrido: keyword scan → LFM confirmation.

        Fase 1 — check_requirements() (zero custo de inferência):
            Varre o prompt por palavras-chave (autenticação, tema escuro, etc.)
            e verifica se o código as implementa.

        Fase 2 — LFM-230M (sob demanda):
            Se a fase 1 encontrar violações, chama o Sentinela (ollama_lfm)
            para confirmar com inferência semântica leve.
        """
        violations, _ = FailureAnalysisAgent.check_requirements(prompt, code)
        if not violations:
            return []

        # Fase 2: Confirmação semântica via LFM-230M
        confirmed = []
        lfm_prompt = LFM_CONFIRM_PROMPT.format(
            request=prompt[:2000], code=code[:3000]
        )

        try:
            lfm_result = await asyncio.wait_for(
                cognitive_dispatch(
                    node_id="sentinel",
                    prompt=lfm_prompt,
                    task_type="validation",
                ),
                timeout=30.0,
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning(
                "[SENTINEL] LFM timeout/erro (%s) — mantendo %d violações keyword",
                exc, len(violations),
            )
            return violations

        if not lfm_result or '"compliant": true' in lfm_result:
            return []

        for v in violations:
            cat = v.get("category", "")
            req = v.get("requirement", "")
            chk = v.get("check", "")
            if any(term in lfm_result.lower() for term in [req.lower(), chk.lower(), cat.lower()]):
                confirmed.append(v)

        return confirmed or violations

    async def monitor_and_report(
        self,
        task_id: str,
        prompt: str,
        code_future: asyncio.Future,
    ) -> None:
        """Wrapper que loga o resultado da monitoria (útil para debugging)."""
        await self.monitor_task(task_id, prompt, code_future)
