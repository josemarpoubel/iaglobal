# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
#  iaglobal/graphs/nodes/no_code_executor.py

"""
Code Executor — executa ou salva código, retorna arquivo final no formato correto.
Totalmente em conformidade com as seções 2, 3 e 4 do AGENTS.md.
Comunica com OmniMind e AcetylcholineBus para troca de mensagens.
"""
import os
import time
import logging
import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, Tuple

from iaglobal.security.sandbox_executor import SandboxExecutor
from iaglobal._paths import save_result_artifact, RESULTS_DIR, _detect_extension, TEMP_DIR
from iaglobal.memory.memory_error import record_error
from iaglobal.obsidian.omnimind import omni_mind
from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL
from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage

logger = logging.getLogger(__name__)
_sandbox = SandboxExecutor(timeout=30)
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


_EXECUTABLE_EXTS = {".py"}
_RUNNABLE_EXTS = {".sh": ["bash"], ".rb": ["ruby"], ".pl": ["perl"]}
_STATIC_EXTS = {
    ".html", ".css", ".js", ".ts", ".json", ".xml", ".yaml", ".yml",
    ".md", ".txt", ".sql", ".php", ".aspx", ".cshtml", ".dockerfile",
}


def _clean_code(raw: str) -> Tuple[str, str]:
    if raw.startswith("```"):
        lines = raw.split("\n")
        fence_lang = lines[0].lstrip("`").strip()
        code = "\n".join(lines[1:])
        if code.endswith("```"):
            code = code[:-3].strip()
        return code, fence_lang
    return raw.strip(), ""


async def run_code_executor(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa e isola códigos gerados em sandbox de forma assíncrona.
    Mapeia os resultados e telemetria para o JointOptimizationLoop.
    Comunica com OmniMind e AcetylcholineBus.
    """
    start_time = time.time()
    resolved_model = "code_generator_source"
    
    # Garante bus iniciado
    _ensure_bus_started()
    
    # Registra agente na OmniMind
    omni_mind.registrar_agente(
        agent_id="code_executor",
        nome="CodeExecutor",
        geracao=0,
        linhagem=GENESIS_HASH_OFFICIAL,
        metadados={"purpose": "run_execute_save"}
    )
    
    # Consulta OmniMind para orientação existencial
    orientacao = omni_mind.consultar(
        agent_id="code_executor",
        pergunta=f"Executar código para: {ctx.get('task', '')[:80]}",
        contexto={"phase": "execution"}
    )
    logger.info("[EXECUTOR] Orientação OmniMind: %s", orientacao.guidance[:100])
    
    # Consulta subconsciente (Obsidian) para intuição de execução
    from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
    subconscious = SubconsciousAPI()
    intuição_exec = await subconscious.sussurrar_intuicao(["#execution", "#sandbox", "#static"])
    logger.info("[EXECUTOR] Intuição do subconsciente: %s", intuição_exec[:100] if intuição_exec else 'vazio')
    
    memory = ctx.get("memory", {})
    task = str(ctx.get("input", {}).get("task", ""))
    
    # Prioriza frontend_builder sobre coder/multi_coder
    raw_code = (memory.get("frontend_builder", {}).get("output", "") or
                memory.get("frontend_builder", {}).get("output", "") or
                memory.get("coder", {}).get("output", "") or
                memory.get("multi_coder", {}).get("output", ""))
    
    if not raw_code:
        logger.warning("[EXECUTOR] Nenhum código detectado para execução.")
        return {
            "output": "", "final_file": None, "executed": False, "success": True,
            "execution_metrics": {"model": resolved_model, "success": True, "latency": 0.0, "cost": 0.0}
        }
    
    cleaned, fence_lang = _clean_code(raw_code)
    if len(cleaned) < 10:
        return {
            "output": "", "final_file": None, "executed": False, "success": True,
            "execution_metrics": {"model": resolved_model, "success": True, "latency": 0.0, "cost": 0.0}
        }
    
    ext = _detect_extension(cleaned, task)
    logger.info("[EXECUTOR] %d chars, ext=%s, fence=%s", len(cleaned), ext, fence_lang or "-")
    
    output_text = ""
    error = None
    saved = None
    violacoes = []  # Inicializado para todos os caminhos
    
    try:
        # --- 1. ARQUIVOS ESTÁTICOS ---
        pdf_found = None
        if ext in _STATIC_EXTS:
            output_text = cleaned
            project_dir = await asyncio.to_thread(save_result_artifact, task=task, files={}, code=output_text)
            if project_dir:
                out_path = Path(project_dir) / f"output{ext}"
                await asyncio.to_thread(out_path.write_text, output_text, encoding="utf-8")
                saved = str(out_path)
            logger.info("[EXECUTOR] Arquivo estático salvo de forma assíncrona: %s", saved)

        # --- 2. PYTHON / SANDBOX ---
        elif ext in _EXECUTABLE_EXTS:
            logger.info("[EXECUTOR] Executando código na sandbox isolada...")
            # Protege contra travamentos síncronos se a chamada da Sandbox não for nativamente async
            if asyncio.iscoroutinefunction(_sandbox.execute):
                result = await _sandbox.execute(cleaned)
            else:
                result = await asyncio.to_thread(_sandbox.execute, cleaned)
                
            output_text = result.get("output", "") or ""
            error = result.get("erro") or result.get("error")
            violacoes = result.get("violacoes", [])
            
            if violacoes:
                security_msg = "; ".join(
                    v if isinstance(v, str) else v.get("message", str(v))
                    for v in violacoes[:5]
                )
                logger.warning("[EXECUTOR] Violacao de seguranca: %s", security_msg)
                await asyncio.to_thread(
                    record_error, "security", security_msg,
                    {"task": task[:100], "violacoes": violacoes}
                )
                error = error or "SecurityViolation"
            
            if error:
                logger.warning("[EXECUTOR] Erro retornado pela Sandbox: %s", error)
                if not violacoes:
                    await asyncio.to_thread(record_error, "code_executor", str(error), {"task": task[:100]})

            pdf_found = None
            sandbox_work_dir = None
            if ext == ".py":
                # Scan BOTH sandbox_dir AND /tmp for generated PDFs
                sandbox_work_dir = str(TEMP_DIR / "sandbox_exec")
                
                def _scan_pdf():
                    # Scan BOTH sandbox_dir AND /tmp for generated PDFs
                    search_dirs = [sandbox_work_dir, "/tmp"]
                    for search_dir in search_dirs:
                        if not search_dir:
                            continue
                        for f in Path(search_dir).rglob("*.pdf"):
                            try:
                                if f.stat().st_size > 100:
                                    return str(f)
                            except FileNotFoundError:
                                continue
                    return None
                pdf_found = await asyncio.to_thread(_scan_pdf)

            # Só salva se output_text não está vazio ou não há erro
            if output_text or not error:
                project_dir = await asyncio.to_thread(save_result_artifact, task=task, files={}, code=output_text)
                if project_dir:
                    out_path = Path(project_dir) / ("output.pdf" if pdf_found and not error else f"output{ext}")
                    if pdf_found and not error:
                        await asyncio.to_thread(shutil.copy, pdf_found, out_path)
                        saved = str(out_path)
                        output_text = f"PDF gerado com sucesso e copiado para: {saved}"
                    else:
                        await asyncio.to_thread(out_path.write_text, output_text, encoding="utf-8")
                        saved = str(out_path)

        # --- 3. EXECUTÁVEIS ALTERNATIVOS (BASH, NODE, PHP) ---
        elif ext in _RUNNABLE_EXTS:
            # Usa NamedTemporaryFile seguro em gerenciador de contexto para auto-excluir do disco
            def _run_external_interpreter():
                import subprocess
                with tempfile.NamedTemporaryFile(suffix=ext, mode="w", delete=False, encoding="utf-8") as temp_file:
                    temp_file.write(cleaned)
                    temp_file_path = temp_file.name
                
                try:
                    cmd = _RUNNABLE_EXTS[ext] + [temp_file_path]
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=False)
                    return r.stdout, (r.stderr if r.returncode != 0 else None)
                except Exception as e:
                    return "", str(e)
                finally:
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)

            output_text, error = await asyncio.to_thread(_run_external_interpreter)
            
            project_dir = await asyncio.to_thread(save_result_artifact, task=task, files={}, code=output_text)
            if project_dir:
                out_path = Path(project_dir) / f"output{ext}"
                await asyncio.to_thread(out_path.write_text, output_text, encoding="utf-8")
                saved = str(out_path)

        # Fallback de varredura global se nenhum caminho direto salvou o artefato
        if not saved:
            def _fallback_scan():
                for pattern in ("*.pdf", "*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.svg", "*.ico"):
                    for f in Path(RESULTS_DIR).rglob(pattern):
                        try:
                            if f.stat().st_size > 100:
                                return str(f)
                        except FileNotFoundError:
                            continue
                return None
            saved = await asyncio.to_thread(_fallback_scan)

        latency_ms = (time.time() - start_time) * 1000.0
        
        # Considera sucesso técnico se o interpretador/sandbox rodou sem capotar o nó
        is_success = error is None

        security_feedback = "; ".join(
            v if isinstance(v, str) else v.get("message", str(v))
            for v in violacoes[:5]
        ) if violacoes else ""

        # Publica resultado no AcetylcholineBus
        bus = _get_bus()
        await bus.publish(
            AgentMessage(
                sender="code_executor",
                receiver="memory_writer",
                type="execution_complete",
                payload={
                    "output": output_text,
                    "final_file": saved,
                    "extension": ext,
                    "success": is_success,
                    "timestamp": time.time()
                },
                priority=7
            )
        )

        return {
            "output": output_text, "executed": True, "final_file": saved, 
            "extension": ext, "exec_error": error, "success": is_success,
            "security_feedback": security_feedback,
            "execution_metrics": {
                "model": resolved_model,
                "success": is_success,
                "latency": latency_ms,
                "cost": 0.0  # Execução local em infraestrutura de sandbox
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.warning("[EXECUTOR] Falha crítica de processamento: %s", e)
        await asyncio.to_thread(record_error, "code_executor", str(e), {"task": task[:100]})
        
        # Publica erro no bus
        bus = _get_bus()
        await bus.publish(
            AgentMessage(
                sender="code_executor",
                receiver="failure_analysis",
                type="execution_failed",
                payload={"error": str(e), "task": task[:100]},
                priority=9
            )
        )
        
        return {
            "output": "", "executed": False, "final_file": None, "exec_error": str(e), "success": False,
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

