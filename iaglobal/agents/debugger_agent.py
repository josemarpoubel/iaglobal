# iaglobal/agents/debugger_agent.py

import re
from typing import Optional
from iaglobal.models.task import Task
from iaglobal.execution.executor import executar
from iaglobal.providers.provider_router import route_generate, resolve_model
from iaglobal.utils.logger import logger
from iaglobal.security.ast_gateway import ASTGateway


class DebuggerAgent:
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts
        self.ast_gateway = ASTGateway()

        # Captura traceback completo do Python
        self.pattern = re.compile(
            r"Traceback \(most recent call last\):[\s\S]*?(?=\n[A-Za-z_].*Error:|\Z)"
        )

    def extract_error(self, output: str) -> Optional[str]:
        """Extrai traceback do output do executor"""
        if not output:
            return None

        match = self.pattern.search(output)
        return match.group(0) if match else None

    def build_fix_prompt(self, task: Task, error: str, code: str) -> str:
        return f"""
Você é um agente de debug.

O código abaixo falhou ao executar:

--- CÓDIGO ---
{code}

--- ERRO ---
{error}

Tarefa original:
{task.description if hasattr(task, "description") else "N/A"}

Corrija o código mantendo a intenção original.
Retorne APENAS o código corrigido, sem explicações.
"""

    def run(self, task: Task) -> dict:
        """
        Executa e tenta corrigir automaticamente erros de execução.
        """
        code = task.code
        last_error = None

        for attempt in range(1, self.max_attempts + 1):
            logger.info(f"[DebuggerAgent] Tentativa {attempt}/{self.max_attempts}")

            # Segurança AST antes de executar
            try:
                self.ast_gateway.validate(code)
            except Exception as e:
                logger.error(f"[ASTGateway] Código inválido: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "code": code,
                }

            # Executa código
            output = executar(code)

            # Verifica erro
            error = self.extract_error(output)

            if not error:
                logger.info("[DebuggerAgent] Execução bem-sucedida")
                return {
                    "success": True,
                    "output": output,
                    "code": code,
                }

            last_error = error
            logger.warning(f"[DebuggerAgent] Erro detectado:\n{error}")

            # Gera correção via LLM
            prompt = self.build_fix_prompt(task, error, code)
            response = route_generate(resolve_model(str(task)), prompt, task_type="debug")

            # Atualiza código corrigido
            code = response.strip()

        logger.error("[DebuggerAgent] Falha após máximo de tentativas")

        return {
            "success": False,
            "error": last_error,
            "code": code,
        }

    def corrigir_codigo(self, codigo: str, erro: str, task: str) -> str:
        """
        Método esperado pelos testes.
        Tenta corrigir o código e retorna versão corrigida ou original em falha.
        """

        try:
            prompt = f"""
    Você é um agente de debug.

    Corrija o código abaixo:

    --- CÓDIGO ---
    {codigo}

    --- ERRO ---
    {erro}

    Tarefa:
    {task}

    Retorne APENAS o código corrigido.
    """

            response = route_generate(resolve_model(str(task)), prompt, task_type="debug")
            codigo_corrigido = self._extrair_codigo_puro(response)

            if not codigo_corrigido:
                return codigo

            return codigo_corrigido

        except Exception as e:
            logger.warning(f"⚠️ [DebuggerAgent] Falha ao corrigir código: {e} — mantendo original.")
            return codigo


    def _extrair_codigo_puro(self, texto: str) -> str:
        """
        Remove markdown ```python ... ``` e retorna só código limpo.
        """

        if not texto:
            return ""

        # remove bloco markdown ```python ... ```
        match = re.search(r"```(?:python)?\s*([\s\S]*?)```", texto)
        if match:
            return match.group(1).strip()

        return texto.strip()
