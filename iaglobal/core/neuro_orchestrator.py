# iaglobal/core/neuro_orchestrator.py

import time
import asyncio
import logging
from typing import Dict, Any, List, Optional

from iaglobal.providers.provider_router import async_route_generate
from iaglobal.memory.memory_storage import storage
from iaglobal.tools.tool_router import ToolRouter
from iaglobal.tools.search import search_tool
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.graphs.credit import CreditAssignmentEngine

logger = logging.getLogger("NEURO_ORCH")


class NeuroOrchestrator:
    """
    🧠 Orquestrador Neuro-Simbólico

    - Usa BanditPolicy para seleção inteligente de modelos (select_top_n)
    - Executa múltiplos modelos em paralelo via asyncio.gather
    - Todos os resultados alimentam o CreditAssignmentEngine
    """

    def __init__(self, bandit: Optional[BanditPolicy] = None):
        self.memory = storage
        self.tool_router = ToolRouter(tools={"search": search_tool})
        self.credit = bandit.credit if bandit else CreditAssignmentEngine()
        self.bandit = bandit or BanditPolicy(self.credit)

    async def reason(self, task: str) -> Dict[str, Any]:
        logger.info(f"🧠 Neuro reasoning: {task[:120]}")

        memory_context = self.memory.retrieve(task)
        memory_score = self._compute_memory_score(memory_context)

        results = await self._execute_parallel(task)

        best = self._rank_results(results)
        self._store_experience(task, results, best)

        return best

    async def _execute_parallel(self, task: str) -> List[Dict]:
        models = self.bandit.select_top_n(node=task, strategy="general", n=5)

        async def _run_one(model: str) -> Dict:
            t0 = time.time()
            try:
                output = await async_route_generate(model=model, prompt=task, task_type="general", node_id="neuro_orchestrator")
                lat = time.time() - t0
                valid = bool(output and len(output) > 30)
                score = self._score_output(task, output)
                self.credit.record_from_execution(
                    model=model, success=valid, latency=lat, task_type="general",
                    reward=score,
                )
                logger.debug("[NEURO] %s: score=%.2f lat=%.2fs", model.split("/")[-1][:20], score, lat)
                return {"model": model, "output": output, "score": score, "latency": lat}
            except Exception as e:
                return {"model": model, "error": str(e), "score": 0.0, "latency": 0}

        return await asyncio.gather(*[_run_one(m) for m in models])

    def _score_output(self, task: str, output: str) -> float:
        if not output:
            return 0.0
        score = 0.5
        if len(output) > 200:
            score += 0.1
        if "error" in output.lower():
            score -= 0.3
        if task.split()[0] in output:
            score += 0.2
        return max(0.0, min(1.0, score))

    def _rank_results(self, results: List[Dict]) -> Dict[str, Any]:
        valid = [r for r in results if "output" in r]
        if not valid:
            return {"output": None, "score": 0.0}
        best = max(valid, key=lambda x: x["score"])
        return {"output": best["output"], "score": best["score"],
                "model": best["model"], "variant": "bandit_top5"}

    def _store_experience(self, task: str, results: List[Dict], best: Dict):
        try:
            self.memory.store(task, best["output"], metadata={
                "best_score": best["score"], "model": best["model"],
                "variants_tested": len(results), "timestamp": time.time(),
            })
        except Exception as e:
            logger.error(f"Memory store failed: {e}")

    def _compute_memory_score(self, memory_context):
        if not memory_context:
            return 0.5
        if isinstance(memory_context, dict) and "score" in memory_context:
            return float(memory_context["score"])
        return 0.5
