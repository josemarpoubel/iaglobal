# ✅  iaglobal/agents/tester_agent.py

import os
import re
import hashlib
import subprocess
import tempfile
from typing import Union, Dict, Any, List

from iaglobal.models.task import Task

from iaglobal.utils.logger import logger

from iaglobal.providers.provider_router import route_generate, resolve_model
from iaglobal.providers.task_router import detect_task_type

# Caminho da pasta de testes do projeto
TESTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests")


class TesterAgent:
    __test__ = False
    """
    Agente responsável por gerar testes, avaliar soluções e ranquear respostas.

    Agora 100% desacoplado do executor antigo.
    Toda inferência LLM é feita via provider_router.
    """

    def __init__(self, workdir=None):

        self.history: List[Dict[str, Any]] = []
        self.workdir = workdir

    # =========================================================
    # UTIL: extrair código puro de resposta LLM
    # =========================================================

    @staticmethod
    def _extrair_codigo_puro(texto: str) -> str:
        if not texto:
            return ""
        texto = texto.strip()
        texto = re.sub(r"^```(?:python|py)?", "", texto, flags=re.IGNORECASE)
        texto = re.sub(r"```$", "", texto)
        return texto.strip()

    # =========================================================
    # GERAR TESTES
    # =========================================================

    def gerar_testes(self, codigo: str, task: Union[str, Task]) -> str:
        logger.info("🧪 [TESTER AGENT]: Gerando testes...")

        task_text = str(task)

        prompt = f"""
Você é um engenheiro de QA especializado em Python.

Gere testes unitários para validar o código abaixo.

==================== TAREFA ====================
{task_text}

==================== CÓDIGO ====================
{codigo}

==================== REGRAS ====================

* Use pytest
* Crie testes realistas
* Não explique nada
* Retorne apenas código Python
  """

        try:

            modelo = resolve_model(str(task))
            task_type = detect_task_type(task_text)
            resposta = route_generate(modelo, prompt, task_type=task_type)

            if not resposta:
                return ""

            return str(resposta)

        except Exception as e:
            logger.warning(f"⚠️ [TESTER AGENT]: Erro ao gerar testes: {e} — retornando vazio.")
            return ""

    def amalgamar_codigo_e_teste(self, codigo: str, teste: str) -> str:
        return f"""CÓDIGO DO DESENVOLVEDOR:
{codigo}

SUITE DE TESTES:
{teste}"""

    def gerar_bateria_testes(self, tarefa: str, codigo: str) -> str:
        return self.gerar_testes(codigo, tarefa)

    # =========================================================
    # SALVAR E EXECUTAR TESTE EM ARQUIVO .py
    # =========================================================

    def gerar_salvar_e_executar(
        self, codigo: str, task: Union[str, Task]
    ) -> dict:
        """
        Gera teste via LLM, salva em tests/test_gen_<hash>.py,
        executa com pytest e retorna resultado.
        """
        task_text = str(task)

        # 1. Gera o código de teste
        raw = self.gerar_testes(codigo, task)
        if not raw:
            return {"sucesso": False, "output": "Nenhum teste gerado", "arquivo": ""}

        teste_limpo = self._extrair_codigo_puro(raw)
        if not teste_limpo:
            return {"sucesso": False, "output": "Teste vazio após extração", "arquivo": ""}

        # 2. Gera nome único baseado no hash da task + código
        task_hash = hashlib.md5(f"{task_text}{codigo}".encode()).hexdigest()[:12]
        nome_arquivo = f"test_gen_{task_hash}.py"

        # Usa workdir se disponível, senão cai no diretório global de testes
        if self.workdir:
            self.workdir.ensure()
            caminho = str(self.workdir.tests / nome_arquivo)
        else:
            caminho = os.path.join(TESTS_DIR, nome_arquivo)

        # 3. Monta o arquivo com código + teste
        #    O código do desenvolvedor precisa ser importável, então
        #    escrevemos o código como um módulo inline + os testes
        linhas = [
            "# Teste gerado automaticamente pelo TesterAgent",
            "# pylint: skip-file",
            "",
            codigo.strip() if not codigo.strip().startswith("import") else "",
            "",
            teste_limpo,
            "",
        ]
        conteudo = "\n".join(linhas)

        try:
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(conteudo)
            logger.info(f"💾 Teste salvo: {caminho}")
        except Exception as e:
            logger.error(f"❌ Erro ao salvar teste: {e}")
            return {"sucesso": False, "output": str(e), "arquivo": ""}

        # 4. Executa o teste com pytest
        try:
            resultado = subprocess.run(
                ["python", "-m", "pytest", caminho, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            output = resultado.stdout + resultado.stderr
            sucesso = resultado.returncode == 0

            logger.info(
                f"{'✅' if sucesso else '❌'} Teste {nome_arquivo}: "
                f"{'PASSOU' if sucesso else 'FALHOU'}"
            )

            return {
                "sucesso": sucesso,
                "output": output[:2000],
                "arquivo": caminho,
                "returncode": resultado.returncode,
            }

        except subprocess.TimeoutExpired:
            logger.warning(f"⏰ Teste {nome_arquivo} excedeu timeout de 60s")
            return {"sucesso": False, "output": "Timeout", "arquivo": caminho}

        except Exception as e:
            logger.error(f"❌ Erro ao executar pytest: {e}")
            return {"sucesso": False, "output": str(e), "arquivo": caminho}

    # =========================================================
    # EXECUTAR AVALIAÇÃO DE SOLUÇÕES
    # =========================================================

    def avaliar_solucao(
        self,
        codigo: str,
        resultado_execucao: Dict[str, Any],
        task: Union[str, Task]
    ) -> str:
        logger.info("📊 [TESTER AGENT]: Avaliando solução...")

        task_text = str(task)

        prompt = f"""

    Você é um avaliador técnico de código Python.

    Avalie a solução com base no código e no resultado da execução.

    ==================== TAREFA ====================
    {task_text}

    ==================== CÓDIGO ====================

    {codigo}

    ==================== RESULTADO EXECUÇÃO ====================
    Sucesso: {resultado_execucao.get("success", False)}
    Output: {resultado_execucao.get("stdout", "vazio")}
    Erro: {resultado_execucao.get("stderr", "nenhum")}
    Traceback: {resultado_execucao.get("traceback", "nenhum")}

    ==================== INSTRUÇÃO ====================
    Dê uma avaliação técnica com:

    * qualidade do código
    * bugs encontrados
    * confiabilidade
    * melhorias possíveis
      """

        try:
            modelo = resolve_model(task_text)
            task_type = detect_task_type(task_text)
            resposta = route_generate(modelo, prompt, task_type=task_type)

            if not resposta:
                return "Avaliação indisponível (resposta vazia)."

            return str(resposta)

        except Exception as e:
            logger.error(f"❌ [TESTER AGENT]: Falha na avaliação: {e}")
            return "Avaliação indisponível devido a erro de comunicação."

    # =========================================================
    # RANQUEAMENTO DE SOLUÇÕES
    # =========================================================

    def rankear_solucoes(
        self,
        solucoes: List[str],
        task: Union[str, Task]
    ) -> str:
        logger.info("🏁 [TESTER AGENT]: Ranqueando soluções...")

        task_text = str(task)

        blocos = "\n\n".join(
            f"SOLUÇÃO #{i+1}\n{sol}"
            for i, sol in enumerate(solucoes)
        )

        prompt = f"""

    Você é um arquiteto de software responsável por ranquear soluções.

    ==================== TAREFA ====================
    {task_text}

    ==================== SOLUÇÕES ====================
    {blocos}

    ==================== INSTRUÇÃO ====================
    Classifique as soluções da melhor para pior com justificativa técnica.
    Retorne em formato estruturado.
    """

        try:
            modelo = resolve_model(task_text)
            task_type = detect_task_type(task_text)
            resposta = route_generate(modelo, prompt, task_type=task_type)

            if not resposta:
                return "Ranking indisponível."

            return str(resposta)

        except Exception as e:
            logger.error(f"❌ [TESTER AGENT]: Erro ao ranquear soluções: {e}")
            return "Ranking indisponível devido a erro de comunicação."
