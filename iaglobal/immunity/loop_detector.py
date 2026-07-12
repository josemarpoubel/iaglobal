"""LoopDetector — detecta ciclos infinitos no DAG e aciona auto-reparação via ReflexionEngine."""

import logging
from typing import Any, Dict, List, Optional, Callable
from collections import defaultdict

logger = logging.getLogger(__name__)

MAX_EXECUTIONS_PER_NODE = 5


class LoopDetector:
    """Monitora execuções de nós, detecta loops e aciona auto-reparação."""

    def __init__(self, max_executions: int = MAX_EXECUTIONS_PER_NODE, reflexion_fn: Optional[Callable] = None):
        self.max_executions = max_executions
        self._execution_count: Dict[str, int] = defaultdict(int)
        self._reflexion_fn = reflexion_fn  # Function to call for auto-repair

    def set_reflexion_fn(self, fn: Callable):
        """Define a função de auto-reparação (ReflexionEngine.reflect)."""
        self._reflexion_fn = fn

    def record_execution(self, node_name: str, success: bool):
        if not success:
            self._execution_count[node_name] += 1
        else:
            self._execution_count[node_name] = 0

    def detect(self) -> List[Dict[str, Any]]:
        loops = []
        for node, count in self._execution_count.items():
            if count >= self.max_executions:
                loops.append({
                    "node": node,
                    "executions": count,
                    "threshold": self.max_executions,
                    "type": "loop",
                })
        return loops

    def check_and_repair(self, node_name: str, success: bool, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Detecta loop e aciona auto-reparação se ReflexionEngine configurado."""
        self.record_execution(node_name, success)
        count = self._execution_count.get(node_name, 0)
        in_loop = count >= self.max_executions
        
        result = {
            "in_loop": in_loop,
            "node": node_name,
            "executions": count,
        }
        
        if in_loop and self._reflexion_fn and context:
            logger.warning(f"[LOOP-REPAIR] Loop detectado no nó '{node_name}' ({count} tentativas) - acionando ReflexionEngine")
            try:
                repair_result = self._reflexion_fn(context)
                result["repair_triggered"] = True
                result["repair_result"] = repair_result
                # Reset after repair attempt
                self._execution_count[node_name] = 0
                logger.info(f"[LOOP-REPAIR] Reparação concluída: {repair_result.get('status', 'unknown')}")
            except Exception as e:
                result["repair_triggered"] = True
                result["repair_error"] = str(e)
                logger.error(f"[LOOP-REPAIR] Falha na reparação: {e}")
        
        return result

    def check(self, node_name: str, success: bool) -> Dict[str, Any]:
        self.record_execution(node_name, success)
        count = self._execution_count.get(node_name, 0)
        in_loop = count >= self.max_executions
        return {
            "in_loop": in_loop,
            "node": node_name,
            "executions": count,
        }

    def reset(self, node_name: str = ""):
        if node_name:
            self._execution_count[node_name] = 0
        else:
            self._execution_count.clear()
