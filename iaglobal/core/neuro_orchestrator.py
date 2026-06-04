# iaglobal/core/neuro_orchestrator.py

import time
import logging
import concurrent.futures
from typing import Dict, Any, List

from iaglobal.providers.provider_router import route_generate
from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.memory.memory_storage import storage
from iaglobal.core.decision_engine import DecisionEngine
from iaglobal.tools.search import search_tool

logger = logging.getLogger("NEURO_ORCH")


class NeuroOrchestrator:
    """
    🧠 Orquestrador Neuro-Simbólico (Passo 9)

    - Executa múltiplas hipóteses em paralelo
    - Ranqueia respostas por score
    - Usa memória como bias cognitivo
    - Evolui decisões com feedback implícito
    """

    def __init__(self):
        self.memory = storage
        self.decision_engine = DecisionEngine()

        _default_ollama = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        self.agents = ["dev_fast", "dev_safe", "dev_exploratory"]
        self.models = [
            f"ollama/{_default_ollama}",
            "nvidia/meta/llama-3.3-70b-instruct",
            "openrouter/meta-llama/llama-3.1-8b-instruct"
        ]

    # =========================================================
    # ENTRYPOINT COGNITIVO
    # =========================================================

    def reason(self, task: str) -> Dict[str, Any]:
        logger.info(f"🧠 Neuro reasoning: {task[:120]}")

        # 1. MEMORY BIAS (influencia decisão)
        memory_context = self.memory.retrieve(task)
        memory_score = self._compute_memory_score(memory_context)

        # 2. DECISÃO INICIAL (multi-caminho)
        candidates = self._generate_candidates(task, memory_score)

        # 3. EXECUÇÃO PARALELA
        results = self._execute_parallel(task, candidates)

        # 4. RANKING COGNITIVO
        best = self._rank_results(results)

        # 5. MEMÓRIA COMO FEEDBACK
        self._store_experience(task, results, best)

        return best

    # =========================================================
    # CANDIDATE GENERATION
    # =========================================================

    def _generate_candidates(self, task: str, memory_score: float):
        decision = self.decision_engine.decide(
            agents=self.agents,
            models=self.models,
            memory_score=memory_score,
            complexity=min(len(task) / 200, 1.0)
        )

        _default_ollama = ProviderConfig.DEFAULT_OLLAMA_MODEL or "qwen2.5:0.5b"
        return [
            {"model": decision.model, "variant": "primary"},
            {"model": f"ollama/{_default_ollama}", "variant": "safe_fallback"},
            {"model": "nvidia/meta/llama-3.3-70b-instruct", "variant": "creative"},
        ]

    # =========================================================
    # PARALLEL EXECUTION ENGINE
    # =========================================================

    def _execute_parallel(self, task: str, candidates: List[Dict]):
        results = []

        def run(candidate):
            try:

                enhanced_task = self.tool_router.resolve(
                    model_type="local",
                    task=task
                )

                enhanced_task = self.tool_router.prepare_prompt(
                    model_type="local",  # ou "online", dependendo do node
                    task=task
                )

                output = route_generate(model=candidate["model"], prompt=enhanced_task, task_type="general")

                score = self._score_output(task, output)
                return {
                    "model": candidate["model"],
                    "variant": candidate["variant"],
                    "output": output,
                    "score": score
                }
            except Exception as e:
                return {
                    "model": candidate["model"],
                    "error": str(e),
                    "score": 0.0
                }

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futures = [ex.submit(run, c) for c in candidates]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        return results

    # =========================================================
    # SCORING COGNITIVO
    # =========================================================

    def _score_output(self, task: str, output: str) -> float:
        if not output:
            return 0.0

        score = 0.5

        # heurística simples (evoluir depois para LLM judge)
        if len(output) > 200:
            score += 0.1
        if "error" in output.lower():
            score -= 0.3
        if task.split()[0] in output:
            score += 0.2

        return max(0.0, min(1.0, score))

    # =========================================================
    # RANKING
    # =========================================================

    def _rank_results(self, results: List[Dict]) -> Dict[str, Any]:
        valid = [r for r in results if "output" in r]

        if not valid:
            return {"output": None, "score": 0.0}

        best = max(valid, key=lambda x: x["score"])

        return {
            "output": best["output"],
            "score": best["score"],
            "model": best["model"],
            "variant": best["variant"]
        }

    # =========================================================
    # MEMORY AS EXPERIENCE
    # =========================================================

    def _store_experience(self, task: str, results: List[Dict], best: Dict):
        try:
            self.memory.store(
                task,
                best["output"],
                metadata={
                    "best_score": best["score"],
                    "model": best["model"],
                    "variants_tested": len(results),
                    "timestamp": time.time()
                }
            )
        except Exception as e:
            logger.error(f"Memory store failed: {e}")

    # =========================================================
    # MEMORY SCORE
    # =========================================================

    def _compute_memory_score(self, memory_context):
        if not memory_context:
            return 0.5

        if isinstance(memory_context, dict) and "score" in memory_context:
            return float(memory_context["score"])

        return 0.5
