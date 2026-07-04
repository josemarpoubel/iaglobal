# iaglobal/api/__init__.py

"""
iaglobal API — Interface programatica para usar a lib de dentro de outras ferramentas.

Uso:
    from iaglobal.api import IAGlobalAPI

    api = IAGlobalAPI()
    result = api.run_task("crie um bloco genesis em sha3_512")
    print(result["script_path"])

    status = api.get_status()
    print(status["nodes_total"])
"""

import os
import time
import logging
import asyncio
import concurrent.futures

from typing import Optional, Dict, Any, List

from iaglobal.utils.logger import logger

logger = logging.getLogger("ia-global")

class IAGlobalAPI:
    """Interface unificada para o ecossistema iaglobal.

    Inicializa o Orchestrator uma unica vez e expoe metodos
    limpos para executar tarefas, consultar status e aprender.
    """

    def __init__(self, lazy_init: bool = False):
        self._orchestrator = None
        self._initialized = False
        if not lazy_init:
            try:
                loop = asyncio.get_running_loop()
                # Se já estamos em um loop, não podemos usar run_until_complete
                # Deixar para initialize_async ser chamado explicitamente
                logger.debug("[API] Event loop ativo detectado — inicialização adiada para initialize_async()")
            except RuntimeError:
                # Sem loop rodando — inicialização síncrona segura
                self.initialize()

    async def initialize_async(self) -> None:
        """Inicialização async segura — use quando já houver event loop rodando."""
        if self._initialized:
            return
        await self.initialize()

    def initialize(self) -> None:
        """Inicializa o sistema (Orchestrator, Evolution Runtime, Event Bus)."""
        if self._initialized:
            return

        from iaglobal.core.env_loader import load_env
        from iaglobal.cli.bootstrap import bootstrap

        load_env()
        logger.info("[API] Inicializando IAGlobal...")
        t0 = time.time()

        # bootstrap.initialize() é async — precisamos executá-lo em um loop
        import asyncio
        # Executa bootstrap.initialize() de forma síncrona segura,
        # independentemente de haver ou não um event loop rodando.
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            self._orchestrator = new_loop.run_until_complete(bootstrap.initialize())
        finally:
            new_loop.close()

        self._initialized = True
        logger.info("[API] IAGlobal pronto em %.2fs", time.time() - t0)

    @property
    def orchestrator(self):
        if not self._initialized:
            self.initialize()
        return self._orchestrator

    # ── Tarefas ──

    def run_task(self, prompt: str) -> Dict[str, Any]:
        """Executa uma tarefa no pipeline completo.

        Args:
            prompt: Descricao da tarefa (ex: "crie um bloco genesis em sha3_512")

        Returns:
            Dict com:
                - success (bool)
                - response (str | None): codigo gerado
                - script_path (str | None): caminho do arquivo salvo
                - score (float): score final (0-1)
                - error (str | None): mensagem de erro se falhou
                - execution_time (float): tempo total em segundos
        """
        t0 = time.time()
        try:
            result = self.orchestrator.run(prompt)
            elapsed = time.time() - t0
            return {
                "success": getattr(result, "success", False),
                "response": getattr(result, "response", None),
                "script_path": getattr(result, "script_path", None),
                "score": getattr(result, "score", 0.0),
                "error": getattr(result, "error", None),
                "execution_time": round(elapsed, 2),
            }
        except Exception as e:
            return {
                "success": False,
                "response": None,
                "script_path": None,
                "score": 0.0,
                "error": str(e),
                "execution_time": round(time.time() - t0, 2),
            }

    def run_dag(self, prompt: str) -> Dict[str, Any]:
        """Executa apenas o DAG (sem cache, sem persistencia).

        Args:
            prompt: Descricao da tarefa

        Returns:
            Dict com resultado bruto do DAG (raw_results, final_output)
        """
        t0 = time.time()
        try:
            result = self.orchestrator.run_graph_task(prompt)
            elapsed = time.time() - t0
            result["execution_time"] = round(elapsed, 2)
            return result
        except Exception as e:
            return {
                "success": False,
                "final_output": None,
                "error": str(e),
                "execution_time": round(time.time() - t0, 2),
            }

    # ── Status ──

    def get_status(self) -> Dict[str, Any]:
        """Retorna status completo do sistema.

        Returns:
            Dict com: dag, evolution, memory, security, version
        """
        from iaglobal.cli.status import Dashboard

        graph = getattr(self.orchestrator, "graph", None)
        runtime = getattr(self.orchestrator, "evolution_runtime", None)
        evolver = getattr(self.orchestrator, "evolver", None)

        nodes = list(graph.nodes.values()) if graph else []
        evo_nodes = [n for n in nodes if n.name.startswith("evo_")] if graph else []

        status = {
            "version": {"python": os.sys.version.split()[0], "graph_gen": graph.generation if graph else 0},
            "dag": {
                "nodes_total": len(nodes),
                "nodes_core": len(nodes) - len(evo_nodes),
                "nodes_evo": len(evo_nodes),
                "strategies": {},
            },
            "evolution": {"running": False, "cycles": 0, "failures": 0},
            "memory": {"insights": 0, "errors": 0},
            "security": {"modules": 0, "read_paths": 0, "write_paths": 0, "blocked_env": 0},
        }

        if runtime:
            rs = runtime.status()
            status["evolution"] = {
                "running": rs.get("running", False),
                "cycles": rs.get("cycles", 0),
                "failures": rs.get("failures", 0),
                "last_execution": rs.get("last_execution"),
            }

        if evolver:
            status["evolution"]["strategies"] = getattr(evolver, "strategies", [])
            status["evolution"]["mutation_rates"] = getattr(evolver, "strategy_mutation_rates", {})

        if graph and nodes:
            from collections import Counter
            strategy_counts = Counter(n.strategy for n in nodes)
            status["dag"]["strategies"] = dict(strategy_counts)

        try:
            from iaglobal.memory.db_manager import db
            status["memory"]["insights"] = db.count_insights()
        except Exception:
            pass

        try:
            from iaglobal.memory.memory_error import load_errors
            status["memory"]["errors"] = len(load_errors())
        except Exception:
            pass

        try:
            from iaglobal.security.sandbox_rules import SandboxRules
            rules = SandboxRules()
            status["security"]["modules"] = len(rules.allowed_modules)
            status["security"]["read_paths"] = len(rules.allowed_read_paths)
            status["security"]["write_paths"] = len(rules.allowed_write_paths)
            status["security"]["blocked_env"] = len(rules.blocked_env_vars)
        except Exception:
            pass

        return status

    # ── Consulta de aprendizado ──

    def get_insights(
        self,
        agent: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        min_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Recupera aprendizados armazenados pelos agentes.

        Args:
            agent: Filtrar por agente (ex: "reflexion", "orchestrator")
            limit: Maximo de registros
            offset: Paginacao
            min_score: Score minimo

        Returns:
            Lista de dicts com id, agent, task_id, content, score, timestamp
        """
        from iaglobal.memory.db_manager import db
        return db.get_insights(agent=agent, limit=limit, offset=offset, min_score=min_score)

    def count_insights(
        self,
        agent: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> int:
        """Total de aprendizados armazenados."""
        from iaglobal.memory.db_manager import db
        return db.count_insights(agent=agent, min_score=min_score)

    def get_recent_errors(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Ultimos erros registrados."""
        from iaglobal.memory.memory_error import load_errors
        return load_errors()[-limit:]

    # ── Scripts gerados ──

    def list_scripts(self) -> List[Dict[str, Any]]:
        """Lista scripts gerados e persistidos."""
        from iaglobal._paths import SCRIPTS_DIR
        if not SCRIPTS_DIR.exists():
            return []
        scripts = []
        for f in sorted(SCRIPTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if f.suffix == ".py":
                scripts.append({
                    "name": f.name,
                    "path": str(f),
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                })
        return scripts

    def read_script(self, name: str) -> Optional[str]:
        """Le o conteudo de um script gerado."""
        from iaglobal._paths import SCRIPTS_DIR
        path = SCRIPTS_DIR / name
        if path.exists() and path.suffix == ".py":
            return path.read_text(encoding="utf-8")
        return None
