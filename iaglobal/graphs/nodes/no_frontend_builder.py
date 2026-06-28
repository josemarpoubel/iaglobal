# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_frontend_builder.py

"""
Frontend Builder Node — Construtor especializado na camada de interface do usuário (Frontend).
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import logging
import asyncio
from typing import Dict, Any

from iaglobal.agents.coder_agent import CoderAgent
from iaglobal.agents.prompt_improver import PromptImprover, PromptMode
from iaglobal.obsidian.omnimind import omni_mind
from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage

logger = logging.getLogger(__name__)
_improver = PromptImprover()
_bus: AcetylcholineBus = None


def _get_bus():
    global _bus
    if _bus is None:
        _bus = AcetylcholineBus()
    return _bus


def _ensure_bus_started():
    """Garante que o purger está rodando (segura se já existe event loop)."""
    bus = _get_bus()
    try:
        loop = asyncio.get_running_loop()
        if bus._purge_task is None or bus._purge_task.done():
            bus._purge_task = asyncio.create_task(bus._periodic_purge(10.0))
    except RuntimeError:
        pass  # Sem event loop - será iniciado depois


async def run_frontend_builder(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a geração de código frontend de forma assíncrona e não-bloqueante.
    Mapeia latência, custos e sucesso sintático para o JointOptimizationLoop.
    Comunica com OmniMind e AcetylcholineBus para troca de mensagens.
    """
    start_time = time.time()
    resolved_model = "frontend_builder_coder_llm"
    
    # Garante bus iniciado
    _ensure_bus_started()
    
    # Registra agente na OmniMind para propósito existencial
    omni_mind.registrar_agente(
        agent_id="frontend_builder",
        nome="FrontendBuilder",
        geracao=0,
        linhagem="web-interface-builder",
        metadados={"domain": "frontend"}
    )
    
    logger.info("[FRONTEND_BUILDER] Iniciando geração da camada de interface e telas...")
    
# Coleta os dados de forma resiliente do contexto ou das memórias estruturadas
    task = ctx.get("task", "") or str(ctx.get("input", {}).get("task", ""))
    architecture_data = ctx.get("architecture", {}) or ctx.get("memory", {}).get("architecture", {})
    
    # Consulta subconsciente (Obsidian) para intuição de frontend responsivo
    from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
    subconscious = SubconsciousAPI()
    intuição = await subconscious.sussurrar_intuicao(["#frontend", "#responsive", "#mobile"])
    
    # Registra agente na OmniMind para propósito existencial
    omni_mind.registrar_agente(
        agent_id="frontend_builder",
        nome="FrontendBuilder",
        geracao=0,
        linhagem="web-interface-builder",
        metadados={"domain": "frontend", "intuicao": intuição[:100] if intuição else None}
    )
    
    # Consulta OmniMind para orientação existencial
    orientacao = omni_mind.consultar(
        agent_id="frontend_builder",
        pergunta=f"Gerar interface para: {task[:80]}",
        contexto={"architecture": architecture_data, "intuicao": intuição[:500]}
    )
    logger.info("[FRONTEND_BUILDER] Orientação da OmniMind: %s", orientacao.guidance[:120])
    
    # Enriquece o contexto com as decisões de arquitetura anteriores
    contexto_refinado = ("frontend only, inline CSS required, mobile-first responsive design, "
                         "meta viewport mandatory, @media queries for breakpoints, no external CSS files")
    if architecture_data:
        frontend_tech = architecture_data.get("components", [{}, {}, {}]).get("tech", "html")
        contexto_refinado = (f"frontend user interface context using: {frontend_tech}, "
                             f"inline CSS, mobile-first responsive design required, "
                             f"@media (max-width: 768px) for mobile")
    
    try:
        # Aprimora o prompt para frontend com domínio web + responsividade
        if asyncio.iscoroutinefunction(_improver.improve):
            improved_task = await _improver.improve(
                raw_prompt=task,
                domain="web",
                mode=PromptMode.FULL,
            )
        else:
            improved_task = await asyncio.to_thread(
                _improver.improve,
                raw_prompt=task,
                domain="web",
                mode=PromptMode.FULL,
            )
        
        # Inicializa o agente programador
        agent = CoderAgent()
        
        # Garante a execução assíncrona ou desvia para thread pool
        if asyncio.iscoroutinefunction(agent.generate):
            artifact = await agent.generate(task=improved_task, contexto=contexto_refinado)
        else:
            artifact = await asyncio.to_thread(agent.generate, task=improved_task, contexto=contexto_refinado)
            
        # Extração segura de propriedades do artefato gerado
        code_output = artifact.code if hasattr(artifact, "code") else str(artifact)
        files_output = artifact.files if hasattr(artifact, "files") else {}
        
        # Validação de responsividade - injeta @media queries se faltando
        if code_output and "@media" not in code_output and "viewport" in code_output:
            logger.info("[FRONTEND_BUILDER] Injetando media queries para responsividade...")
            # Wrap existing style or add responsive block inside <head>
            if "</style>" in code_output:
                responsive_css = """
        @media (max-width: 768px) {
            .calculator { width: 95%; margin: 10px auto; padding: 15px; }
            .display { font-size: 1.8rem; height: 50px; }
            button { height: 45px; font-size: 1rem; }
            .botoes { grid-template-columns: repeat(4, 1fr); gap: 8px; }
        }
"""
                code_output = code_output.replace("</style>", responsive_css + "</style>")
            elif "<head>" in code_output:
                # Add inline style block before </head>
                responsive_css = """
    <style>
        @media (max-width: 768px) {
            .calculator { width: 95%; margin: 10px auto; padding: 15px; }
            .display { font-size: 1.8rem; height: 50px; }
            button { height: 45px; font-size: 1rem; }
            .botoes { grid-template-columns: repeat(4, 1fr); gap: 8px; }
        }
    </style>
"""
                code_output = code_output.replace("</head>", responsive_css + "</head>")
        
        # Publica mensagem no AcetylcholineBus para code_executor
        bus = _get_bus()
        await bus.publish(
            AgentMessage(
                sender="frontend_builder",
                receiver="code_executor",
                type="frontend_ready",
                payload={
                    "output": code_output,
                    "files": files_output,
                    "timestamp": time.time()
                },
                priority=8
            )
        )
        
        # Portão de segurança: validação básica de saída vazia
        is_success = bool(code_output and len(code_output.strip()) > 5)
        
        if is_success:
            logger.info("[FRONTEND_BUILDER] Interface de usuário gerada com sucesso: %d caracteres.", len(code_output))
        else:
            logger.warning("[FRONTEND_BUILDER] Geração retornou código de interface vazio ou inválido.")

        latency_ms = (time.time() - start_time) * 1000.0

        return {
            "output": code_output,
            "frontend_builder": {
                "output": code_output,
                "files": files_output
            },
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": ctx.get("estimated_cost", 0.015)
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[FRONTEND_BUILDER] Falha crítica no pipeline do Frontend Builder Agent: %s", e)
        
        return {
            "output": "",
            "frontend_builder": {"output": "", "files": {}, "error": str(e)},
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

