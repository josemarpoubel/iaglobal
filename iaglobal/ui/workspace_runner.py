"""
iaglobal/ui/workspace_runner.py
================================
Executa tarefas iaglobal em workspaces Git isolados.
Integra ExecutionGraph com GitWorkspace para criar commits automáticos
de cada resultado de agente.
"""

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from iaglobal.utils.logger import logger
from iaglobal.ui.git_workspace import GitWorkspace, GitWorkspaceError
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.graphs.builder import build_pipeline_from_nodes


class WorkspaceRunnerError(Exception):
    """Erro na execução do workspace."""
    pass


class WorkspaceRunner:
    """Executa tarefas iaglobal em workspaces Git isolados.
    
    Fluxo:
        1. Cria workspace Git isolado
        2. Constrói pipeline de execução (ExecutionGraph)
        3. Executa tarefa
        4. Commita resultado
        5. Retorna métricas e caminho do workspace
    """

    def __init__(self, default_base_path: Optional[Path] = None):
        from iaglobal._paths import PROJECT_ROOT
        self.default_base_path = default_base_path or PROJECT_ROOT
        self._active_workspaces: Dict[str, GitWorkspace] = {}
        self._active_graphs: Dict[str, ExecutionGraph] = {}

    async def run_task(self, task_description: str, execution_id: Optional[str] = None) -> Dict[str, Any]:
        """Executa uma tarefa em workspace isolado.
        
        Args:
            task_description: Descrição da tarefa a executar.
            execution_id: ID de execução opcional (gerado se não fornecido).
            
        Returns:
            Dict com execution_id, success, workspace_path, branch, metrics.
        """
        if not task_description or len(task_description.strip()) < 3:
            raise WorkspaceRunnerError("task_description deve ter pelo menos 3 caracteres")
        
        execution_id = execution_id or str(uuid.uuid4())
        start_time = time.time()
        
        workspace = GitWorkspace(base_path=self.default_base_path)
        
        try:
            # 1. Cria workspace isolado
            workspace_path = workspace.create(execution_id)
            
            self._active_workspaces[execution_id] = workspace
            
            logger.info("[RUNNER] Workspace criado para %s: %s", execution_id, workspace_path)
            
            # 2. Constrói pipeline
            graph = build_pipeline_from_nodes()
            
            self._active_graphs[execution_id] = graph
            
            # 3. Executa tarefa COM TIMEOUT
            input_data = {
                "task": task_description,
                "metadata": {
                    "execution_id": execution_id,
                    "workspace_path": str(workspace_path),
                    "branch": workspace.branch,
                }
            }
            
            try:
                result = await asyncio.wait_for(
                    graph.async_run(input_data, execution_id=execution_id),
                    timeout=300
                )
            except asyncio.TimeoutError:
                raise WorkspaceRunnerError("Timeout após 300s")
            
            duration = time.time() - start_time
            
            # 4. Commita resultado
            commit_message = (
                f"feat: iaglobal task '{task_description[:50]}'\n\n"
                f"Execution ID: {execution_id}\n"
                f"Duration: {duration:.2f}s\n"
                f"Success: {result.get('success', False)}\n"
                f"Nodes: {result.get('nodes_executed', 0)}"
            )
            
            committed = workspace.commit_changes(commit_message)
            
            # 5. Atualizar métricas
            logger.info(
                "[RUNNER] ✅ Tarefa %s concluída em %.2fs",
                execution_id, duration
            )
            
            # 6. Retorna métricas
            return {
                "execution_id": execution_id,
                "success": result.get("success", False),
                "workspace_path": str(workspace_path),
                "branch": workspace.branch,
                "committed": committed,
                "duration": duration,
                "nodes_executed": result.get("nodes_executed", 0),
                "final_output": result.get("final_output", "")[:500],
                "raw_results": result.get("raw_results", {}),
                "execution_metrics": {
                    "model": "workspace_runner",
                    "success": result.get("success", False),
                    "latency": duration,
                    "cost": 0.0,
                    "ivm": 1.0 if result.get("success") else 0.0,
                },
            }
        
        except WorkspaceRunnerError:
            raise
        
        except Exception as e:
            logger.error("[RUNNER] ❌ Falha na execução %s: %s", execution_id, e)
            raise WorkspaceRunnerError(f"Falha ao executar tarefa: {e}")
        finally:
            # Cleanup será chamado explicitamente pelo usuário ou após timeout
            pass

    async def get_status(self, execution_id: str) -> Dict[str, Any]:
        """Retorna status de uma execução em andamento."""
        workspace = self._active_workspaces.get(execution_id)
        graph = self._active_graphs.get(execution_id)
        
        return {
            "execution_id": execution_id,
            "workspace_active": execution_id in self._active_workspaces,
            "workspace_path": str(workspace.path) if workspace else None,
            "branch": workspace.branch if workspace else None,
            "graph_loaded": execution_id in self._active_graphs,
                "recent_commits": workspace.get_recent_commits(3) if workspace else [],
                "diff": workspace.get_diff() if workspace else "",
        }

    async def cleanup_workspace(self, execution_id: str) -> None:
        """Remove workspace de uma execução."""
        workspace = self._active_workspaces.pop(execution_id, None)
        if workspace:
            workspace.cleanup()
        self._active_graphs.pop(execution_id, None)
        logger.info("[RUNNER] Workspace limpo: %s", execution_id)

    async def cleanup_all(self) -> None:
        """Remove todos os workspaces ativos."""
        execution_ids = list(self._active_workspaces.keys())
        for eid in execution_ids:
            await self.cleanup_workspace(eid)


# Singleton global para o runner
_runner: Optional[WorkspaceRunner] = None


def get_workspace_runner() -> WorkspaceRunner:
    """Retorna instância singleton do WorkspaceRunner."""
    global _runner
    if _runner is None:
        _runner = WorkspaceRunner()
    return _runner
