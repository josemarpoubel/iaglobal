# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Debug Unificado Node — Mescla debugger + debug_coder com integração LSP.

Fluxo:
  1. Extrai código das memórias (coder, multi_coder, etc.)
  2. Coleta diagnósticos do LSP validator se disponíveis
  3. Tenta usar SkillDebugUnificado se registrada
  4. Fallback para DebuggerAgent.run() se skill indisponível
  5. Retorna código corrigido + execution_metrics

Integrações:
  - LSP Validator: lê diagnósticos de ctx["memory"]["lsp_validator"]
  - SkillRegistry: usa skill se disponível
  - BanditPolicy: relata sucesso/falha para aprendizado evolutivo
"""
import time
from typing import Dict, Any, Optional

from iaglobal.utils.logger import get_logger
from iaglobal.models.task import Task
from iaglobal.agents.debugger_agent import DebuggerAgent
from iaglobal.validation.js_validator import detect_lang

logger = get_logger("iaglobal.graphs.nodes.debug_unificado")


async def run_debug_unificado(ctx: Dict[str, Any]) -> Dict[str, Any]:
    start = time.time()
    resolved_model = "debug_unificado"

    memory = ctx.get("memory", {})
    task_str = str(ctx.get("input", {}).get("task", ""))

    # Fase 1 — Extrai código das fontes
    code = ""
    sources = ("multi_coder", "coder", "debug_coder", "backend_builder", "frontend_builder", "api_builder")
    for source in sources:
        artifact = memory.get(source, {})
        if isinstance(artifact, str) and artifact.strip():
            code = artifact
            break
        if isinstance(artifact, dict):
            for key in ("output", "code", "content", "integrated_code"):
                val = artifact.get(key)
                if val and isinstance(val, str) and val.strip():
                    code = val
                    break
            if code:
                break
        if hasattr(artifact, "code") and artifact.code:
            code = artifact.code
            break

    if not code:
        logger.warning("[DEBUG_UNIFICADO] Nenhum código encontrado.")
        return {
            "output": "",
            "debug_result": None,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": (time.time() - start) * 1000.0,
                "cost": 0.0,
            },
        }

    # Fase 2 — Coleta diagnósticos do LSP validator
    lsp_errors = []
    lsp_diagnostics = []
    lsp_node = memory.get("lsp_validator", {})
    if isinstance(lsp_node, dict):
        lsp_errors = lsp_node.get("lsp_errors", []) or []
        lsp_diagnostics = lsp_node.get("diagnostics", []) or []

    logger.info(
        "[DEBUG_UNIFICADO] Código=%d chars | LSP erros=%d | diagnostics=%d",
        len(code), len(lsp_errors), len(lsp_diagnostics),
    )

    # Fase 2a — Detecção de linguagem: JS/JSX → rota JS, Python → rota Python
    lang = detect_lang(code)
    if lang in ("js", "jsx", "ts"):
        logger.info("[DEBUG_UNIFICADO] Código %s detectado → rota JS", lang)
        js_result = await _try_js_validator(code)
        syntax_valid = js_result.get("syntax_valid", False)
        if syntax_valid:
            corrected_code = js_result["output"]
            auto_fixed = js_result.get("auto_fixed", False)
            model_used = "js_syntax_sentinel"
            latency_total = (time.time() - start) * 1000.0
            logger.info(
                "[DEBUG_UNIFICADO] Código %s válido | auto_fixed=%s | latency=%.1fms",
                lang, auto_fixed, latency_total,
            )
            return {
                "output": corrected_code,
                "debug_result": {
                    "success": True,
                    "code": corrected_code,
                    "attempts": 0,
                    "model_used": model_used,
                    "auto_fixed_by_sentinel": auto_fixed,
                },
                "execution_metrics": {
                    "model": model_used,
                    "success": True,
                    "latency": latency_total,
                    "cost": 0.0,
                },
            }
        # JS não pôde ser validado — retorna original com info de erro
        logger.warning(
            "[DEBUG_UNIFICADO] Código %s inválido após validação JS | retornando original",
            lang,
        )
        return {
            "output": code,
            "debug_result": {
                "success": True,
                "code": code,
                "attempts": 0,
                "model_used": "js_syntax_sentinel",
                "auto_fixed_by_sentinel": False,
                "syntax_valid": False,
                "error": js_result.get("syntax_error"),
            },
            "execution_metrics": {
                "model": "js_syntax_sentinel",
                "success": True,
                "latency": (time.time() - start) * 1000.0,
                "cost": 0.0,
            },
        }

    # Fase 2b — SyntaxSentinel: tenta corrigir sintaxe Python nativamente
    sentinel_result = await _try_syntax_sentinel(code)
    if sentinel_result.get("auto_fixed") and sentinel_result.get("syntax_valid"):
        corrected_code = sentinel_result["output"]
        model_used = "syntax_sentinel"
        success = True
        attempts = 0
        latency_total = (time.time() - start) * 1000.0
        logger.info(
            "[DEBUG_UNIFICADO] Sintaxe corrigida pelo SyntaxSentinel | latency=%.1fms",
            latency_total,
        )
        return {
            "output": corrected_code,
            "debug_result": {
                "success": success,
                "code": corrected_code,
                "attempts": attempts,
                "model_used": model_used,
                "auto_fixed_by_sentinel": True,
            },
            "execution_metrics": {
                "model": model_used,
                "success": success,
                "latency": latency_total,
                "cost": 0.0,
            },
        }

    # Fase 3 — Tenta usar SkillDebugUnificado (fallback para LLM apenas se necessário)
    corrected_code, model_used, attempts, success = await _tentar_skill(
        code=code,
        lsp_errors=lsp_errors,
        task_str=task_str,
    )

    # Fase 4 — Fallback para DebuggerAgent se skill falhou
    if not success and not corrected_code:
        logger.info("[DEBUG_UNIFICADO] Skill falhou → fallback DebuggerAgent")
        result = await _usar_debugger_agent(code, task_str, lsp_errors)
        corrected_code = result.code
        model_used = result.model_used or resolved_model
        attempts = result.attempts
        success = result.success

    latency = (time.time() - start) * 1000.0

    logger.info(
        "[DEBUG_UNIFICADO] Finalizado | success=%s attempts=%d code=%d chars | latency=%.1fms",
        success, attempts, len(corrected_code or ""), latency,
    )

    return {
        "output": corrected_code or code,
        "debug_result": {
            "success": success,
            "code": corrected_code,
            "attempts": attempts,
            "model_used": model_used,
        },
        "execution_metrics": {
            "model": model_used or resolved_model,
            "success": success,
            "latency": latency,
            "cost": ctx.get("estimated_cost", 0.01) * max(1, attempts),
        },
    }


async def _tentar_skill(
    code: str,
    lsp_errors: list,
    task_str: str,
) -> tuple[Optional[str], Optional[str], int, bool]:
    """
    Tenta usar SkillDebugUnificado + SkillPythonAutocomplete.
    
    Fluxo:
      1. SkillPythonAutocomplete analisa código com Jedi
      2. SkillDebugUnificado usa análise para correção precisa
      3. Retorna código corrigido
    
    Returns:
        (corrected_code, model_used, attempts, success)
    """
    try:
        from iaglobal.evolution.skills.skill_registry import skill_registry
        
        # Tenta skill de autocomplete primeiro para análise
        autocomplete_skill = skill_registry.get("python_autocomplete")
        debug_skill = skill_registry.get("debug_unificado")
        
        if not debug_skill:
            logger.debug("[DEBUG_UNIFICADO] Skill debug não registrada")
            return None, None, 0, False
        
        logger.info("[DEBUG_UNIFICADO] Usando SkillDebugUnificado + Autocomplete")
        
        # Se autocomplete disponível, faz análise prévia
        jedi_analysis = {}
        if autocomplete_skill:
            try:
                task_analise = Task(
                    objective="Analisar código",
                    code=code,
                    context={"lsp_errors": lsp_errors},
                )
                result_analise = await autocomplete_skill.execute(task_analise)
                jedi_analysis = result_analise.get("analysis", {})
                logger.info(
                    "[DEBUG_UNIFICADO] Jedi análise: %d issues, %d symbols",
                    len(jedi_analysis.get("issues", [])),
                    len(jedi_analysis.get("symbols", [])),
                )
            except Exception as e:
                logger.debug("[DEBUG_UNIFICADO] Autocomplete falhou: %s", e)
        
        # Executa skill de debug com análise do Jedi
        task = Task(
            objective=task_str or "Corrigir código Python",
            code=code,
            context={
                "lsp_errors": lsp_errors,
                "task": task_str,
                "jedi_analysis": jedi_analysis,
            },
        )
        
        corrected = await debug_skill.execute(task)
        
        success = bool(corrected and len(corrected.strip()) > len(code.strip()) * 0.5)
        return corrected, "skill_debug_unificado+jedi", 1, success
        
    except ImportError as e:
        logger.debug("[DEBUG_UNIFICADO] Skill indisponível: %s", e)
        return None, None, 0, False
    except Exception as e:
        logger.warning("[DEBUG_UNIFICADO] Skill falhou: %s", e)
        return None, None, 0, False


async def _usar_debugger_agent(
    code: str,
    task_str: str,
    lsp_errors: list,
) -> Any:
    """
    Fallback para DebuggerAgent.run().
    """
    from iaglobal.agents.debugger_agent import DebuggerAgent
    
    agent = DebuggerAgent(max_attempts=3)
    task = Task(
        objective=task_str or "Corrigir código Python",
        code=code,
        context={"lsp_errors": lsp_errors},
    )
    
    # Se há erro de sintaxe no LSP, usa _repair_code diretamente
    has_syntax_error = any(
        "syntax" in err.lower() or "'('" in err
        for err in (lsp_errors or [])
    )
    
    if has_syntax_error and lsp_errors:
        logger.info("[DEBUG_UNIFICADO] Erro sintaxe → reparo direto")
        repaired, model = await agent._repair_code(
            task=task,
            code=code,
            error=lsp_errors[0],
        )
        from iaglobal.agents.debugger_agent import DebugResult
        return DebugResult(
            success=bool(repaired and len(repaired.strip()) > 10),
            code=repaired,
            attempts=1,
            model_used=model,
            execution_time=0.0,
        )
    
    # Sem erro de sintaxe → execução normal
    return await agent.run(task)


async def _try_syntax_sentinel(code: str) -> Dict[str, Any]:
    """
    Wrapper para invocar o SyntaxSentinel de forma segura.
    
    Importa o módulo sob demanda para evitar circular imports.
    """
    try:
        from iaglobal.graphs.nodes.syntax_sentinel import run_syntax_sentinel
        return await run_syntax_sentinel({"memory": {"coder": code}, "input": {"task": ""}})
    except Exception as e:
        logger.debug("[DEBUG_UNIFICADO] SyntaxSentinel indisponível: %s", e)
        return {
            "output": code,
            "syntax_valid": False,
            "syntax_error": None,
            "auto_fixed": False,
            "execution_metrics": {"model": "syntax_sentinel", "success": True, "latency": 0.0, "cost": 0.0},
        }


async def _try_js_validator(code: str) -> Dict[str, Any]:
    """
    Wrapper para invocar o JS SyntaxSentinel de forma segura.
    
    Usa esprima para validar e corrigir JS/JSX nativamente.
    Importa sob demanda para evitar circular imports.
    """
    try:
        from iaglobal.graphs.nodes.js_syntax_sentinel import run_js_syntax_sentinel
        return await run_js_syntax_sentinel({"memory": {"coder": code}, "input": {"task": ""}})
    except Exception as e:
        logger.debug("[DEBUG_UNIFICADO] JS SyntaxSentinel indisponível: %s", e)
        return {
            "output": code,
            "syntax_valid": False,
            "syntax_error": None,
            "auto_fixed": False,
            "lang": None,
            "execution_metrics": {"model": "js_syntax_sentinel", "success": True, "latency": 0.0, "cost": 0.0},
        }
