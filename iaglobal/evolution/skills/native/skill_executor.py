# iaglobal/evolution/skills/skill_executor.py

import copy
import threading
from typing import Dict, Any, Optional

from iaglobal.utils.logger import logger
from .skill import Skill, ExecutionPolicy
from .skill_registry import skill_registry

from typing import TYPE_CHECKING, Any, Dict

# O TYPE_CHECKING só é lido pelo analisador de tipos (não causa importação circular)
if TYPE_CHECKING:
    from .skill import Skill, ExecutionPolicy


class SkillExecutionError(Exception):
    """Erro customizado para falhas de execução."""


class SkillExecutor:
    """
    Executor de skills com gestão concorrente e suporte a fallback dinâmico.
    """

    def __init__(self, registry=None):
        self.registry = registry or skill_registry
        # Lock local para blindar transações complexas de leitura-antes-da-escrita
        self._execution_lock = threading.Lock()

    def _build_contract_ctx(self, skill: Skill, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Constrói um dicionário plano com cópias seguras para evitar mutações indesejadas.
        """
        contract_ctx = {}

        input_data = ctx.get("input", {})
        task = (
            input_data.get("task", "")
            if isinstance(input_data, dict)
            else str(input_data)
        )
        if task:
            contract_ctx["task"] = task

        memory = ctx.get("memory", {})

        for node_name, node_result in memory.items():
            if not isinstance(node_result, dict):
                continue
            output = node_result.get("output")
            if output is not None:
                if hasattr(output, "code") and output.code:
                    contract_ctx["code"] = output.code
                    contract_ctx["artifact"] = output
                elif isinstance(output, str) and output:
                    contract_ctx["code"] = output
                score_val = getattr(output, "score", None)
                if score_val is not None:
                    contract_ctx["score"] = score_val
                error_val = getattr(output, "runtime_error", None)
                if error_val:
                    contract_ctx["error"] = error_val
                task_val = getattr(output, "task", None)
                if task_val:
                    contract_ctx["task"] = task_val

                output_text = (
                    output.code
                    if hasattr(output, "code")
                    else (output if isinstance(output, str) else "")
                )
                if output_text:
                    node_skill = self.registry.get(node_name)
                    if node_skill:
                        for out_name in node_skill.outputs:
                            if out_name not in contract_ctx:
                                contract_ctx[out_name] = output_text

            for key, value in node_result.items():
                if key in skill.inputs and key not in ("output",):
                    contract_ctx[key] = copy.deepcopy(value)

        for key in skill.inputs:
            if key in ctx:
                contract_ctx[key] = copy.deepcopy(ctx[key])

        if "workdir" in ctx:
            contract_ctx["workdir"] = ctx["workdir"]

        if "execution_result" in skill.inputs:
            contract_ctx["execution_result"] = copy.deepcopy(memory)

        return contract_ctx

    async def execute(
        self,
        skill_name: str,
        ctx: Dict[str, Any],
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        from ..utils.skill_quarantine import quarantine

        if quarantine.is_quarantined(skill_name):
            raise SkillExecutionError(f"Skill '{skill_name}' está em quarentena")

        # Busca segura da skill ativa ou versão histórica
        skill = (
            self.registry.get_version(skill_name, version)
            if version
            else self.registry.get(skill_name)
        )

        if not skill:
            raise SkillExecutionError(f"Skill '{skill_name}' não encontrada ou inativa")

        # Validação atômica e coordenada da política SINGLE_RUN
        if skill.execution_policy == ExecutionPolicy.SINGLE_RUN:
            with self._execution_lock:
                if self.registry.get_usage_count(skill_name) > 0:
                    logger.info(
                        "[SKILL] '%s' já executada (single-run) — pulando", skill_name
                    )
                    return {"skipped": True, "reason": "single-run já executada"}

        contract_ctx = self._build_contract_ctx(skill, ctx)

        missing = [inp for inp in skill.inputs if inp not in contract_ctx]
        if missing:
            available = list(contract_ctx.keys())
            raise SkillExecutionError(
                f"Skill '{skill_name}' requer inputs faltando: {missing}. "
                f"Disponíveis no contexto: {available}"
            )

        # RESOLUÇÃO DO BUG 1: Se a skill nativa não tiver run_fn definida,
        # aciona o mecanismo genérico de execução base/LLM mapeado no execute estrutural da Skill
        if not skill.run_fn:
            logger.warning(
                "[SKILL] '%s' sem run_fn. Redirecionando para barramento genérico da instância.",
                skill_name,
            )
            # Para evitar recursão infinita, usamos uma lógica alternativa ou deixamos estourar apenas se o execute falhar por completo
            try:
                # Caso queira disparar um comportamento padrão via LLM integrado ao grafo:
                return {
                    "status": "delegated_to_node",
                    "skill": skill_name,
                    "context": contract_ctx,
                }
            except Exception as e:
                raise SkillExecutionError(
                    f"Erro no barramento de fallback para '{skill_name}': {e}"
                )

        logger.info("[SKILL] Executando: %s v%s", skill_name, skill.version)

        try:
            result = await skill.run_fn(
                contract_ctx
            )  # Passa o contexto filtrado do contrato, e não o ctx gigante bruto

            if not skill.validate_output(result):
                raise SkillExecutionError(
                    f"Skill '{skill_name}' produziu output inválido"
                )

            self.registry.increment_usage(skill_name)
            return result

        except Exception as e:
            logger.error("[SKILL] Falha ao executar '%s': %s", skill_name, e)
            from ..utils.skill_quarantine import quarantine

            quarantine.record_failure(skill_name, str(e), impact=1)
            raise SkillExecutionError(f"Falha na execução de '{skill_name}': {e}")

    async def execute_with_fallback(
        self,
        skill_name: str,
        ctx: Dict[str, Any],
        version: Optional[str] = None,
        _depth: int = 0,
        _visited: Optional[set] = None,
    ) -> Dict[str, Any]:
        try:
            return await self.execute(skill_name, ctx, version)
        except SkillExecutionError as e:
            skill = self.registry.get(skill_name)
            if not skill or _depth >= 2:
                raise

            if _visited is None:
                _visited = set()
            _visited.add(skill_name)

            contract_ctx = self._build_contract_ctx(skill, ctx)
            available = set(contract_ctx.keys())
            alternatives = self.registry.find_alternatives(
                skill_name, available, _visited
            )

            for alt in alternatives:
                if alt.name in _visited:
                    continue
                _visited.add(alt.name)
                logger.info(
                    "[SKILL] Tentando alternativa '%s' no lugar de '%s'",
                    alt.name,
                    skill_name,
                )
                try:
                    result = await self.execute_with_fallback(
                        alt.name, ctx, version, _depth + 1, _visited
                    )
                    logger.info(
                        "[SKILL] Alternativa '%s' executou com sucesso no lugar de '%s'",
                        alt.name,
                        skill_name,
                    )
                    return result
                except SkillExecutionError as alt_e:
                    logger.warning(
                        "[SKILL] Alternativa '%s' também falhou: %s", alt.name, alt_e
                    )
                    continue

            logger.debug(
                "[SKILL] Nenhuma alternativa viável para '%s' — lançando exceção primária",
                skill_name,
            )
            raise

    def can_execute(self, skill_name: str) -> bool:
        return self.registry.get(skill_name) is not None


# Instância global coordenada
skill_executor = SkillExecutor()
