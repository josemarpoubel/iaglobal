from typing import Dict, Any, Optional

from iaglobal.utils.logger import logger
from .skill import Skill, ExecutionPolicy
from .skill_registry import skill_registry


class SkillExecutionError(Exception):
    """Erro durante execução de uma skill."""


class SkillExecutor:
    """
    Executor de skills.

    Gerencia o ciclo de vida de execução:
    1. Resolve skill do registry
    2. Verifica contrato (inputs disponíveis no contexto de execução)
    3. Executa via run_fn
    4. Valida output
    5. Registra resultado
    """

    def __init__(self, registry=None):
        self.registry = registry or skill_registry

    def _build_contract_ctx(self, skill: Skill, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Constrói um dicionário plano com todos os valores disponíveis no
        contexto de execução que podem corresponder aos inputs declarados da skill.
        """
        contract_ctx = {}

        input_data = ctx.get("input", {})
        task = input_data.get("task", "") if isinstance(input_data, dict) else str(input_data)
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
                plan_val = getattr(output, "code", None)
                if plan_val:
                    contract_ctx["plan"] = plan_val
            for key, value in node_result.items():
                if key in skill.inputs and key not in ("output",):
                    contract_ctx[key] = value

        for key in skill.inputs:
            if key in ctx:
                contract_ctx[key] = ctx[key]

        if "workdir" in ctx:
            contract_ctx["workdir"] = ctx["workdir"]

        if "execution_result" in skill.inputs:
            contract_ctx["execution_result"] = memory

        return contract_ctx

    def execute(
        self,
        skill_name: str,
        ctx: Dict[str, Any],
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executa uma skill pelo nome com verificação de contrato completa.

        Args:
            skill_name: Nome da skill a executar
            ctx: Contexto completo de execução (input, memory, workdir)
            version: Versão específica (opcional)

        Returns:
            Dict com resultado da execução

        Raises:
            SkillExecutionError: se skill não encontrada, inputs faltando,
                                 ou execução falhar
        """
        if version:
            skill = self.registry.get_version(skill_name, version)
        else:
            skill = self.registry.get(skill_name)

        if not skill:
            raise SkillExecutionError(f"Skill '{skill_name}' não encontrada ou inativa")

        contract_ctx = self._build_contract_ctx(skill, ctx)

        missing = [inp for inp in skill.inputs if inp not in contract_ctx]
        if missing:
            available = list(contract_ctx.keys())
            raise SkillExecutionError(
                f"Skill '{skill_name}' requer inputs faltando: {missing}. "
                f"Disponíveis no contexto: {available}"
            )

        if skill.execution_policy == ExecutionPolicy.SINGLE_RUN:
            if self.registry.get_usage_count(skill_name) > 0:
                logger.info("[SKILL] '%s' já executada (single-run) — pulando", skill_name)
                return {"skipped": True, "reason": "single-run já executada"}

        if not skill.run_fn:
            raise SkillExecutionError(f"Skill '{skill_name}' não tem run_fn definida")

        logger.info("[SKILL] Executando: %s v%s", skill_name, skill.version)

        try:
            result = skill.run_fn(ctx)

            if not skill.validate_output(result):
                raise SkillExecutionError(
                    f"Skill '{skill_name}' produziu output inválido"
                )

            self.registry.increment_usage(skill_name)

            return result

        except Exception as e:
            logger.error("[SKILL] Falha ao executar '%s': %s", skill_name, e)
            raise SkillExecutionError(f"Falha na execução de '{skill_name}': {e}")

    def execute_with_fallback(
        self,
        skill_name: str,
        ctx: Dict[str, Any],
        version: Optional[str] = None,
        _depth: int = 0,
    ) -> Dict[str, Any]:
        """
        Executa uma skill com fallback automático para skills alternativas.

        Se a skill primária falhar por contrato (inputs faltando), busca
        no registry outras skills com outputs compatíveis cujos inputs
        estejam disponíveis no contexto atual.

        Args:
            skill_name: Nome da skill primária
            ctx: Contexto completo de execução
            version: Versão específica (opcional)
            _depth: Profundidade recursiva (segurança, máx 2)

        Returns:
            Dict com resultado da execução

        Raises:
            SkillExecutionError: se skill e todas as alternativas falharem
        """
        try:
            return self.execute(skill_name, ctx, version)
        except SkillExecutionError as e:
            skill = self.registry.get(skill_name)
            if not skill or _depth >= 2:
                raise

            contract_ctx = self._build_contract_ctx(skill, ctx)
            available = set(contract_ctx.keys())
            alternatives = self.registry.find_alternatives(skill_name, available)

            for alt in alternatives:
                logger.info("[SKILL] Tentando alternativa '%s' no lugar de '%s'", alt.name, skill_name)
                try:
                    result = self.execute_with_fallback(alt.name, ctx, version, _depth + 1)
                    logger.info("[SKILL] Alternativa '%s' executou com sucesso no lugar de '%s'", alt.name, skill_name)
                    return result
                except SkillExecutionError as alt_e:
                    logger.warning("[SKILL] Alternativa '%s' também falhou: %s", alt.name, alt_e)
                    continue

            logger.debug("[SKILL] Nenhuma alternativa viável para '%s' de %s candidatos — fallback node.run/LLM", skill_name, len(alternatives))
            raise

    def validate_contract(self, skill_name: str, context: Dict[str, Any]) -> bool:
        """Verifica se uma skill pode ser executada com o contexto dado."""
        skill = self.registry.get(skill_name)
        if not skill:
            return False
        return skill.can_execute(context)

    def can_execute(self, skill_name: str) -> bool:
        """Verifica se a skill está registrada e ativa."""
        return self.registry.get(skill_name) is not None

    def get_execution_count(self, skill_name: str) -> int:
        return self.registry.get_usage_count(skill_name)


skill_executor = SkillExecutor()
