# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_documentation.py

"""
Documentation Node — Redator técnico do ecossistema iaglobal.
Gera relatórios, manuais e documentos formatados com telemetria ativa para o Bandit Policy.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.agent_base import AgentBase
from iaglobal.memory.memory_error import record_error
from iaglobal.graphs.communication.acetylcholine_bus import AgentMessage

logger = logging.getLogger(__name__)


# Palavras-chave que ativam schema de saída estruturado (análise, não código)
_ANALYSIS_KEYWORDS = {"analise", "análise", "analisar", "diagnóstico", "diagnostico",
                      "gargalo", "melhorar", "revisão", "revisao", "avaliar", "avalie"}

# Schema de saída para tarefas de análise
_ANALYSIS_SYSTEM_PROMPT = (
    "Voce e um analista tecnico gerando relatorios estruturados.\n"
    "NAO gere codigo. Siga EXATAMENTE o schema de saida abaixo:\n"
    "\n"
    "# Titulo do Relatorio\n"
    "\n"
    "## Diagnostico\n"
    "(analise tecnica detalhada do estado atual)\n"
    "\n"
    "## Gargalos Identificados\n"
    "(lista priorizada de problemas e limitacoes)\n"
    "\n"
    "## Plano de Acao\n"
    "(passos concretos para resolucao, ordenados por impacto)\n"
    "\n"
    "## Conclusao\n"
    "(sintese das recomendacoes)\n"
    "\n"
    "Preencha CADA seção com conteudo substancial baseado na tarefa."
)

# Instância singleton do agent para reutilização
_documentation_agent = None


def _get_documentation_agent() -> AgentBase:
    """Retorna instancia singleton do DocumentationAgent."""
    global _documentation_agent
    if _documentation_agent is None:
        _documentation_agent = AgentBase(agent_name="documentation")
    return _documentation_agent


async def run_documentation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a geração de documentação técnica de forma assíncrona e não-bloqueante.
    Mapeia latência, custo de tokens e sucesso sintático para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "documentation_agent_llm"
    
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))

    ag_mailbox = memory.get("agentmailbox", {}) or ctx.get("agentmailbox", {})
    bus = ag_mailbox.get("_agent_bus") or ctx.get("_agent_bus")
    inbox = ag_mailbox.get("_mailbox_manager") or ctx.get("_mailbox_manager")
    
    # Consumo seguro e em background da caixa de entrada
    if bus is not None and inbox is not None:
        def _consume_inbox():
            mailbox = inbox.get_or_create("documentation")
            return mailbox.process_inbox(max_messages=5)
            
        msgs = await asyncio.to_thread(_consume_inbox)
        if msgs:
            for msg in msgs:
                logger.info("[DOCUMENTATION] Mensagem recebida de %s: type=%s", msg.sender, msg.type)

    # Coleta de forma resiliente as saídas dos nós anteriores para contextualização
    coder_output = memory.get("coder", {}).get("output", "") or memory.get("multi_coder", {}).get("output", "")
    built_prompt = memory.get("prompt_builder", {}).get("built_prompt", "") or memory.get("prompt_builder", {}).get("output", "")

    if not task and not coder_output and not built_prompt:
        await asyncio.to_thread(record_error, "documentation", "Empty task context", {"task": task})
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "", "document": "",
            "execution_metrics": {"model": resolved_model, "success": False, "latency": latency_ms, "cost": 0.0}
        }

    specialization = ctx.get("input", {}).get("_specialization", {}).get("coder", "")
    base_content = coder_output or built_prompt or task

    is_analysis = any(kw in task.lower() for kw in _ANALYSIS_KEYWORDS)

    if is_analysis:
        system = _ANALYSIS_SYSTEM_PROMPT
    else:
        system = (
            "Voce e um redator tecnico gerando documentos formatados e prontos para publicacao.\n"
            "Formate o documento de forma limpa, bem estruturada, com secoes claras.\n"
            "Nao gere codigo — gere o documento final completo.\n"
            "Se o formato solicitado for PDF, inclua a estrutura completa do documento "
            "(titulo, introducao, secoes, conclusao) em formato texto rico."
        )
    if specialization:
        system = specialization

    prompt = (
        f"{system}\n\n"
        f"Tarefa original: {task}\n\n"
        f"Conteudo base:\n{base_content}\n\n"
        f"Gere o documento final completo e formatado, pronto para ser salvo como PDF. "
        f"Inclua titulo, secoes, listas e todo o conteudo necessario."
    )

    try:
        logger.info("[DOCUMENTATION] Disparando inferência assíncrona para redação técnica do documento...")
        
        # Usa AgentBase para chamar BanditPolicy
        agent = _get_documentation_agent()
        doc = await agent._call_llm(
            prompt=prompt,
            task_type="documentation",
            timeout=60.0
        )
        
        # Portão de segurança: validação de tamanho mínimo da documentação gerada
        is_success = bool(doc and len(doc) > 100)
        
        if is_success:
            logger.info("[DOCUMENTATION] Documento técnico gerado com sucesso: %d caracteres.", len(doc))
            
            # Publicação reativa e assíncrona no AcetylcholineBus para alertar o result_agent
            if bus is not None:
                msg = AgentMessage(
                    sender="documentation", 
                    receiver="result_agent",
                    type="doc_ready",
                    payload={"document": doc, "task": task},
                )
                if asyncio.iscoroutinefunction(bus.publish):
                    await bus.publish(msg)
                else:
                    await asyncio.to_thread(bus.publish, msg)
                logger.info("[DOCUMENTATION] Evento 'doc_ready' injetado no barramento com sucesso.")
                
            latency_ms = (time.time() - start_time) * 1000.0
            
            return {
                "output": doc,
                "document": doc,
                "execution_metrics": {
                    "model": resolved_model,
                    "success": True,
                    "latency": latency_ms,
                    "cost": ctx.get("estimated_cost", 0.008)
                }
            }
            
        # Caso a IA retorne um documento em branco ou excessivamente curto
        await asyncio.to_thread(record_error, "documentation", "Empty/short document", {"task": task[:100]})
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "", "document": "",
            "execution_metrics": {"model": resolved_model, "success": False, "latency": latency_ms, "cost": ctx.get("estimated_cost", 0.002)}
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[DOCUMENTATION] Falha crítica no pipeline do Documentation Agent: %s", e)
        await asyncio.to_thread(record_error, "documentation", str(e), {"task": task[:100]})
        
        return {
            "output": "",
            "document": "",
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }