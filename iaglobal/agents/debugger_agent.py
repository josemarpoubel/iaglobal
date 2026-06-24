# iaglobal/agents/debugger_agent.py

from __future__ import annotations

import asyncio
import hashlib
import re
import time

from dataclasses import dataclass
from typing import Optional

from iaglobal.execution.executor import executar
from iaglobal.graphs.policy import PolicyRegistry
from iaglobal.models.task import Task
from iaglobal.security.ast_gateway import ASTGateway
from iaglobal.utils.logger import get_logger


logger = get_logger("iaglobal.agents.debugger_agent")


@dataclass(slots=True)
class DebugResult:
    success: bool
    code: str
    output: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    model_used: Optional[str] = None
    execution_time: float = 0.0


class DebuggerAgent:
    """
    IA Global Self-Healing Debug Agent

    Responsabilidades:

    1. Validar AST
    2. Executar código
    3. Detectar erro
    4. Solicitar correção ao LLM
    5. Revalidar código corrigido
    6. Evitar loops infinitos
    7. Atualizar política Bandit
    8. Produzir telemetria
    """

    TRACEBACK_PATTERN = re.compile(
        r"Traceback \(most recent call last\):[\s\S]*?(?=\n[A-Za-z_].*Error:|\Z)"
    )

    CODE_BLOCK_PATTERN = re.compile(
        r"```(?:python)?\s*([\s\S]*?)```",
        re.IGNORECASE,
    )

    def __init__(
        self,
        max_attempts: int = 5,
        enable_self_healing: bool = True,
    ):
        self.max_attempts = max_attempts
        self.enable_self_healing = enable_self_healing

        self.ast_gateway = ASTGateway()

        self.policy_registry = PolicyRegistry()
        self.bandit = self.policy_registry.get("debugger")

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    async def run(self, task: Task) -> DebugResult:
        """
        Fluxo principal do agente.
        """

        start_time = time.perf_counter()

        code = task.code

        previous_versions = set()

        last_error = None
        last_model = None

        for attempt in range(1, self.max_attempts + 1):

            logger.info(
                "Attempt=%s/%s",
                attempt,
                self.max_attempts,
            )

            try:
                self._validate(code)
            except Exception as e:
                last_error = str(e)
                logger.exception("AST validation failed")
                return DebugResult(
                    success=False,
                    code=code,
                    error=str(e),
                    attempts=attempt,
                    execution_time=time.perf_counter() - start_time,
                )

            output = await executar("", {"task": code})

            error = self.extract_error(output)

            if not error:

                self._reward_success(
                    model=last_model,
                    attempt=attempt,
                )

                return DebugResult(
                    success=True,
                    code=code,
                    output=output,
                    attempts=attempt,
                    model_used=last_model,
                    execution_time=time.perf_counter() - start_time,
                )

            last_error = error

            logger.warning(
                "Execution failed: %s",
                error[:300],
            )

            code_hash = self._hash(code)

            if code_hash in previous_versions:

                logger.error(
                    "[DebuggerAgent] Infinite correction loop detected"
                )

                break

            previous_versions.add(code_hash)

            if not self.enable_self_healing:
                break

            code, last_model = await self._repair_code(
                task=task,
                code=code,
                error=error,
            )

        return DebugResult(
            success=False,
            code=code,
            error=last_error,
            attempts=self.max_attempts,
            model_used=last_model,
            execution_time=time.perf_counter() - start_time,
        )

    # ==========================================================
    # SELF HEALING
    # ==========================================================

    async def _repair_code(
        self,
        task: Task,
        code: str,
        error: str,
    ) -> tuple[str, Optional[str]]:

        prompt = self.build_fix_prompt(
            task=task,
            error=error,
            code=code,
        )

        model = self.bandit.select_model(
            node="debugger_agent",
            strategy="debug",
        )

        logger.info(
            "Repair model=%s",
            model,
        )
        try:
            response = await self.bandit.async_execute_model(
                model=model, prompt=prompt, task_type="debug",
            )
            fixed_code = self._extract_code(response)
            if not fixed_code:
                logger.warning(
                    "[DebuggerAgent] Empty model response"
                )
                return code, model

            try:
                self._validate(fixed_code)
            except Exception as e:
                logger.warning(
                    "[DebuggerAgent] Generated code rejected: %s",
                    e,
                )
                return code, model

            self.bandit.update_policy(
                node="debugger_agent",
                model=model,
                strategy="debug",
                success=True,
                latency=0.5,
                reward=0.75,
            )
            return fixed_code, model

        except Exception as e:
            logger.exception(
                "[DebuggerAgent] Self-healing failure"
            )
            self.bandit.update_policy(
                node="debugger_agent",
                model=model,
                strategy="debug",
                success=False,
                latency=1.0,
                reward=0.0,
            )
            return code, model

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate(self, code: str) -> None:
        result = self.ast_gateway.parse(code)
        if not result.valid:
            raise ValueError("; ".join(result.errors))

    # ==========================================================
    # ERROR EXTRACTION
    # ==========================================================

    def extract_error(
        self,
        output: Optional[str],
    ) -> Optional[str]:

        if not output:
            return None

        match = self.TRACEBACK_PATTERN.search(output)

        return match.group(0) if match else None

    # ==========================================================
    # PROMPTS
    # ==========================================================

    def build_fix_prompt(
        self,
        task: Task,
        error: str,
        code: str,
    ) -> str:

        return f"""
Você é um especialista em Python.

Corrija o código abaixo.

Retorne SOMENTE código Python válido.

========================
CÓDIGO
========================

{code}

========================
ERRO
========================

{error}

========================
TAREFA ORIGINAL
========================

{getattr(task, "description", "N/A")}
"""

    # ==========================================================
    # UTILITIES
    # ==========================================================

    def _extract_code(
        self,
        text: str,
    ) -> str:

        if not text:
            return ""

        match = self.CODE_BLOCK_PATTERN.search(text)

        if match:
            return match.group(1).strip()

        return text.strip()

    def _hash(self, content: str) -> str:
        return hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()

    def _reward_success(
        self,
        model: Optional[str],
        attempt: int,
    ) -> None:

        if not model:
            return

        reward = max(
            0.1,
            1.0 - (attempt * 0.1),
        )

        self.bandit.update_policy(
            node="debugger_agent",
            model=model,
            strategy="debug",
            success=True,
            latency=0.1,
            reward=reward,
        )

    # ==========================================================
    # COMPATIBILITY API
    # ==========================================================

    async def corrigir_codigo(
        self,
        codigo: str,
        erro: str,
        task: str,
    ) -> str:

        fake_task = Task(
            objective=task,
            context={"code": codigo},
        )

        repaired_code, _ = await self._repair_code(
            task=fake_task,
            code=codigo,
            error=erro,
        )

        return repaired_code


