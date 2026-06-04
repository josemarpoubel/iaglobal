# iaglobal/agents/coder_agent.py

import re
import ast
import traceback

from typing import Union
from iaglobal.models.task import Task
from iaglobal.execution.executor import executar
from iaglobal.utils.logger import logger
from iaglobal.providers.provider_router import route_generate, resolve_model
from iaglobal.validation.engine import ValidationEngine


class CoderAgent:
    def __init__(self, temperatura: float = 0.5, estilo: str = "direto, minimalista"):
        self.temperatura = temperatura
        self.estilo = estilo

    def gerar_codigo(self, task: Union[str, 'Task'], contexto: str = "", erros_contexto: str = "", security_feedback: str = "") -> str:
        task_str = task.text if hasattr(task, 'text') else str(task)
        
        # Define os modelos (ajuste conforme sua configuração)
        MODELO_ONLINE = resolve_model(task_str)
        MODELO_LOCAL = "qwen2.5:0.5b" # Exemplo de modelo no Ollama
        
        def chamar_modelo(nome_modelo, prompt):
            return executar(nome_modelo, {
                "task": prompt,
                "system_constraints": [],
                "temperature": self.temperatura
            })

        logger.info(f"💻 [CODER AGENT]: Tentando gerar via {MODELO_LOCAL} (estilo: {self.estilo})...")

        # Nova abordagem: Removemos a string restrita de BIBLIOTECAS_PERMITIDAS
        # Delegação total de segurança para o Sandbox e para a validação dinâmica do Critic v2

        security_section = ""
        if security_feedback:
            security_section = f"""
    VIOLAÇÃO DE SEGURANÇA OU FALHA EM EXECUÇÃO DETECTADA NA TENTATIVA ANTERIOR:
    {security_feedback}
    ATENÇÃO: Corrija o código imediatamente removendo chamadas inseguras ou imports restritos pelo Sandbox.
    """

        # 2. Prompt atualizado com liberdade de imports e diretrizes estritas de qualidade
        prompt = f"""
    Você é um Engenheiro de Software Sênior. 
    Estilo: {self.estilo}.
    Contexto: {contexto or "Nenhum."}
    Erros a reparar: {erros_contexto or "Nenhum."}
    Tarefa: {task_str}{security_section}

    DIRETRIZES DE LOGGING (OBRIGATÓRIO):
    - NÃO use a função nativa `print()`.
    - Sempre utilize o módulo nativo `logging`.
    - Inicialize o logger no escopo global do código gerado usando: `logger = logging.getLogger(__name__)`.
    - Use `logger.info()` para fluxos normais e `logger.error()` ou `logger.exception()` para capturar falhas.

    REGRAS DE ARQUITETURA E SEGURANÇA:
    - Você está AUTORIZADO a usar qualquer biblioteca padrão do Python (ex: json, html, os, sys, etc.) ou pacotes instalados no ambiente para resolver a tarefa com máxima eficiência.
    - Evite trechos redundantes ou código que possa falhar no ambiente de execução do Sandbox.

    "REGRAS DE RETORNO: Retorne ESTRITAMENTE o código gerado dentro do bloco de markdown correspondente à linguagem da tarefa (ex: ```html ... ```, ```python ... ```, ```css ... ```). Não inclua explicações textuais fora do bloco.
    
    """
        
        codigo = ""
        # Estratégia de Fallback (Bandit / Multi-Modelo)
        for modelo_alvo in [MODELO_ONLINE, MODELO_LOCAL]:
            try:
                logger.info(f"⚙️ Tentando execução com: {modelo_alvo}")
                resposta = chamar_modelo(modelo_alvo, prompt)
                codigo = self._extrair_codigo_puro(resposta)
                
                if codigo and self._sintaxe_valida(codigo):
                    return codigo
                else:
                    logger.warning(f"⚠️ [CODER AGENT]: Código inválido ou vazio retornado por {modelo_alvo}.")
            
            except Exception:
                logger.warning(f"⚠️ [CODER AGENT]: Falha no {modelo_alvo} — tentando próximo modelo.")
                continue

        logger.critical("🚨 [CODER AGENT]: Todos os modelos falharam na geração.")
        return ""

    def _extrair_codigo_puro(self, resposta: str) -> str:
        import re
        # Captura blocos ```python, ```html, ```css ou apenas ```
        match = re.search(r"```(?:python|html|css|javascript)?\s*(.*?)\s*```", resposta, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return resposta.strip()

    def _extrair_codigo_por_ast(self, texto: str) -> str:
        """
        Extrai automaticamente o maior bloco Python válido.
        """

        linhas = texto.splitlines()

        inicio_codigo = None

        marcadores = (
            "def ",
            "class ",
            "import ",
            "from ",
            "@",
            "async def ",
            "if __name__",
        )

        for i, linha in enumerate(linhas):

            if linha.lstrip().startswith(marcadores):
                inicio_codigo = i
                break

        if inicio_codigo is None:
            return ""

        codigo = "\n".join(linhas[inicio_codigo:])

        while codigo:

            try:
                ast.parse(codigo)
                return codigo.strip()

            except SyntaxError as erro:

                linhas_codigo = codigo.splitlines()

                if erro.lineno is not None:

                    indice = erro.lineno - 1

                    if indice < len(linhas_codigo):
                        linhas_codigo.pop(indice)
                    else:
                        linhas_codigo.pop()

                else:
                    linhas_codigo.pop()

                codigo = "\n".join(linhas_codigo)

        return ""

    def _encontrar_maior_bloco_python(self, texto: str) -> str:
        """
        Procura o maior trecho sintaticamente válido de Python
        dentro de um texto arbitrário.
        """

        linhas = texto.splitlines()

        melhor_codigo = ""
        maior_tamanho = 0

        for inicio in range(len(linhas)):

            buffer = []

            for fim in range(inicio, len(linhas)):

                buffer.append(linhas[fim])

                candidato = "\n".join(buffer).strip()

                if not candidato:
                    continue

                try:
                    ast.parse(candidato)

                    tamanho = len(candidato)

                    if tamanho > maior_tamanho:
                        maior_tamanho = tamanho
                        melhor_codigo = candidato

                except SyntaxError:
                    pass

        return melhor_codigo

    def _sintaxe_valida(self, codigo: str) -> bool:
        """
        Verifica a validade do código através de análise estática (AST)
        e validação lógica pelo motor de testes.
        """
        if not codigo or not codigo.strip():
            logger.warning("🔍 [VALIDAÇÃO]: Código vazio ou apenas espaços.")
            return False
            
        try:
            # 1. Verificação de Sintaxe via AST (nativa do Python)
            # Isso detecta erros de indentação, sintaxe inválida, tokens inesperados, etc.
            ast.parse(codigo)
            
        except SyntaxError as e:
            logger.error(f"❌ [VALIDAÇÃO]: Erro de sintaxe detectado: {e.msg} na linha {e.lineno}")
            return False
        except Exception as e:
            logger.error(f"❌ [VALIDAÇÃO]: Erro inesperado na análise AST: {e}")
            return False

        # 2. Validação Semântica/Lógica via ValidationEngine
        try:
            result = ValidationEngine().validate(codigo)
            if not result.valid:
                logger.warning(f"⚠️ [VALIDAÇÃO]: Código falhou na validação de regras: {getattr(result, 'message', 'Sem detalhes')}")
            return result.valid
            
        except Exception as e:
            logger.error(f"❌ [VALIDAÇÃO]: Falha crítica no ValidationEngine: {e}")
            return False
