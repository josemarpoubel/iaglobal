# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Skill Debug Unificado — Correção de código com diagnóstico LSP.

Diferenciais:
  - Lê erros do LSP validator (sintaxe, imports, etc.)
  - Constrói prompt específico baseado no tipo de erro
  - Usa BanditPolicyEvolution para seleção inteligente de modelo
  - Registra recompensa baseada no sucesso da correção
  - Evita execução de código com erro de sintaxe (vai direto para correção)
"""

import time
from typing import List

from iaglobal.evolution.skills.native.skill import Skill
from iaglobal.models.task import Task
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.skills.debug_unificado")


class SkillDebugUnificado(Skill):
    """
    Skill de correção de código com integração LSP.

    Fluxo:
      1. Lê erros do LSP validator (se disponíveis)
      2. Se há erro de sintaxe → pula execução, vai para correção
      3. Constrói prompt específico baseado no erro
      4. Seleciona modelo via BanditPolicyEvolution
      5. Tenta corrigir, valida, registra recompensa
    """

    def __init__(self):
        super().__init__(
            name="debug_unificado",
            description="Corrige código Python com diagnóstico LSP (sintaxe, imports, etc.)",
            inputs=["code", "lsp_errors", "task"],
            outputs=["corrected_code"],
            constraints=["python_syntax_valid", "imports_resolved"],
            tags=["debug", "correction", "lsp", "self-healing"],
            version="1.0.0",
        )
        self.debugger_agent = None

    async def execute(self, task: Task) -> str:
        """
        Executa correção de código com contexto LSP.

        Args:
            task: Task com code, context["lsp_errors"], context["task"]

        Returns:
            Código corrigido ou código original se falhar
        """
        start = time.time()

        # Extrai código e erros LSP
        code = getattr(task, "code", None) or task.context.get("code", "")
        lsp_errors = task.context.get("lsp_errors", [])
        task_desc = task.context.get("task", task.objective)

        if not code:
            logger.warning("[SKILL-DEBUG] Nenhum código para corrigir")
            return ""

        logger.info(
            "[SKILL-DEBUG] Iniciando | code=%d chars | lsp_errors=%d | task=%s",
            len(code),
            len(lsp_errors),
            task_desc[:50] if task_desc else "N/A",
        )

        # Verifica se há erro de sintaxe no LSP → pula execução, vai direto para correção
        has_syntax_error = any(
            "syntax" in err.lower() or "parêntese" in err.lower() or "'('" in err
            for err in (lsp_errors or [])
        )

        if has_syntax_error:
            logger.info("[SKILL-DEBUG] Erro de sintaxe detectado → correção direta")
            return await self._corrigir_direto(code, lsp_errors, task_desc)

        # Sem erro de sintaxe → tenta execução normal com DebuggerAgent
        logger.info("[SKILL-DEBUG] Sem erro de sintaxe → execução normal")
        if self.debugger_agent is None:
            from iaglobal.agents.debugger_agent import DebuggerAgent

            self.debugger_agent = DebuggerAgent(max_attempts=3)
        result = await self.debugger_agent.run(task)

        elapsed = time.time() - start
        logger.info(
            "[SKILL-DEBUG] Finalizado | success=%s | attempts=%d | elapsed=%.2fs",
            result.success,
            result.attempts,
            elapsed,
        )

        return result.code if result.success else code

    async def _corrigir_direto(
        self,
        code: str,
        lsp_errors: List[str],
        task_desc: str,
    ) -> str:
        """
        Correção direta sem execução — para erros de sintaxe.

        Usa _repair_code do DebuggerAgent com prompt específico do erro LSP.
        """
        # Constrói prompt específico baseado no erro LSP
        erro_especifico = lsp_errors[0] if lsp_errors else "erro de sintaxe"

        fake_task = Task(
            objective=task_desc or "Corrigir código Python",
            context={"code": code, "lsp_errors": lsp_errors},
        )

        logger.info(
            "[SKILL-DEBUG] Reparando código | erro_lsp=%s",
            erro_especifico[:100],
        )

        # Usa _repair_code diretamente com o erro LSP
        if self.debugger_agent is None:
            from iaglobal.agents.debugger_agent import DebuggerAgent

            self.debugger_agent = DebuggerAgent(max_attempts=3)
        repaired_code, model_used = await self.debugger_agent._repair_code(
            task=fake_task,
            code=code,
            error=erro_especifico,
        )

        # Valida código reparado
        try:
            self.debugger_agent._validate(repaired_code)
            logger.info("[SKILL-DEBUG] Código reparado validado com sucesso")
            return repaired_code
        except Exception as e:
            logger.warning(
                "[SKILL-DEBUG] Código reparado inválido: %s",
                str(e)[:100],
            )
            return code  # Retorna original se validação falhar

    def build_prompt_com_lsp(
        self,
        code: str,
        lsp_errors: List[str],
        task_desc: str,
    ) -> str:
        """
        Constrói prompt específico baseado nos erros do LSP.

        Exemplos:
          - "SyntaxError: '(' was never closed" → "Feche o parêntese na linha X"
          - "Import não encontrado: 'modulo_x'" → "Remova ou corrija o import"
        """
        erro_principal = lsp_errors[0] if lsp_errors else "erro desconhecido"

        # Detecta tipo de erro
        if "syntax" in erro_principal.lower() or "'('" in erro_principal:
            tipo = "sintaxe"
            instrucao = (
                "Corrija a sintaxe Python. Verifique parênteses, colchetes, indentação."
            )
        elif "import" in erro_principal.lower():
            tipo = "import"
            instrucao = "Corrija os imports. Remova imports não utilizados ou corrija nomes de módulos."
        elif "undefined" in erro_principal.lower():
            tipo = "variável indefinida"
            instrucao = "Defina todas as variáveis antes de usá-las."
        else:
            tipo = "desconhecido"
            instrucao = "Analise e corrija o erro."

        return f"""Você é um especialista em Python.

TAREFA: {task_desc or "Corrigir código Python"}

TIPO DE ERRO: {tipo}
ERRO ESPECÍFICO: {erro_principal}

INSTRUÇÃO: {instrucao}

CÓDIGO COM ERRO:
```python
{code}
```

Retorne APENAS o código corrigido, sem explicações, sem blocos markdown.
"""


# Instância global para registro
skill_debug_unificado = SkillDebugUnificado()
