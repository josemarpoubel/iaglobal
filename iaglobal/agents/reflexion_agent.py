# ✅ `iaglobal/agents/reflexion_agent.py` (REFATORADO)

from typing import Union

from iaglobal.models.task import Task
from iaglobal.reflection.reflexion_engine import reflexion_loop, extract_code_block
from iaglobal.utils.logger import logger

from iaglobal.providers.provider_router import route_generate, resolve_model


class ReflexionAgent:
    """
    Agente de reflexão e auto-melhoria.

    Agora totalmente desacoplado do executor antigo.
    Toda inferência LLM passa pelo provider_router.
    """

    def __init__(self):
        pass

    # =========================================================
    # CICLO DE AUTO-REFLEXÃO
    # =========================================================

    def executar_com_reflexao(
        self,
        model_fn,
        prompt: str,
        max_iterations: int = 5
    ) -> str:
        logger.info("🔄 [REFLEXION AGENT]: Iniciando ciclo de auto-correção...")
        return reflexion_loop(model_fn, prompt, max_iterations)

    # =========================================================
    # ANÁLISE DE RESULTADO
    # =========================================================

    def analisar_resultado(
        self,
        codigo: str,
        resultado_sandbox: dict,
        task: Union[str, Task]
    ) -> str:
        logger.info("🔍 [REFLEXION AGENT]: Analisando qualidade da execução...")

        task_text = str(task)

        prompt = f"""
Você é um engenheiro de software sênior especializado em análise de qualidade.

Avalie criticamente o código e sua execução em sandbox.

==================== TAREFA ====================
{task_text}

==================== CÓDIGO GERADO ====================
{codigo}

==================== RESULTADO DA EXECUÇÃO ====================
Status: {"Sucesso" if resultado_sandbox.get("sucesso") else "Falha"}
Output: {resultado_sandbox.get("output", "vazio")}
Erro: {resultado_sandbox.get("erro", "nenhum")}

==================== INSTRUÇÃO ====================
Forneça uma análise objetiva com:

* causas do erro (se houver)
* problemas de lógica
* melhorias concretas
  """

        try:
            modelo = resolve_model(task_text)

            resposta = route_generate(modelo, prompt, task_type="reflection")

            if not resposta:
                return "Análise não disponível (resposta vazia do provider)."

            return str(resposta)

        except Exception as e:
            logger.warning(f"⚠️ [REFLEXION AGENT]: Falha na análise: {e} — retornando fallback.")
            return "Análise não disponível devido a erro de comunicação."

    # =========================================================
    # SUGESTÃO DE MELHORIA
    # =========================================================

    def sugerir_melhoria(
        self,
        codigo: str,
        analise: str,
        task: Union[str, Task]
    ) -> str:
        logger.info("💡 [REFLEXION AGENT]: Gerando melhorias...")

        task_text = str(task)

        prompt = f"""

Você é um arquiteto de software especialista em refatoração.

Com base na análise abaixo, reescreva o código corrigindo problemas e melhorando qualidade.

==================== TAREFA ====================
{task_text}

==================== ANÁLISE ====================
{analise}

==================== CÓDIGO ATUAL ====================

{codigo}

==================== REGRAS ====================

* Retorne APENAS código Python
* Não explique nada
* Não use markdown fora do bloco de código
* Preserve a lógica original
* Corrija apenas o necessário
  """

        try:
            modelo = resolve_model(task_text)

            resposta = route_generate(modelo, prompt, task_type="reflection")

            if not resposta:
                return codigo

            return extract_code_block(resposta)

        except Exception as e:
            logger.warning(f"⚠️ [REFLEXION AGENT]: Falha ao gerar melhoria: {e} — mantendo código original.")
            return codigo
