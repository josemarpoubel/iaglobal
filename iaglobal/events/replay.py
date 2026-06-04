import json
from typing import Dict, Any, List, Optional, Tuple

from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.graphs.telemetry import ExecutionEvent
from iaglobal.events import DecisionEvent, store
from iaglobal.utils.logger import logger


class DecisionReplaySystem:

    @staticmethod
    def load(execution_id: str) -> List[Dict[str, Any]]:
        return store.replay(execution_id)

    @staticmethod
    def summary(execution_id: str) -> Optional[Dict[str, Any]]:
        rows = store.replay(execution_id)
        if not rows:
            return None

        result = {"execution_id": execution_id, "events": len(rows)}
        seen = set()
        for row in rows:
            data = row.get("_parsed") or {}
            step = data.get("step", "")

            if step in seen:
                continue
            seen.add(step)

            if step == "model_selection":
                if data.get("selected") is not None:
                    result["model"] = data["selected"]
                if data.get("metadata", {}).get("strategy"):
                    result["strategy"] = data["metadata"]["strategy"]
                if data.get("scores_snapshot") is not None:
                    result["scores"] = data["scores_snapshot"]
                if data.get("exploration") is not None:
                    result["exploration"] = data["exploration"]
            elif step == "execution_metrics":
                if data.get("reward_signal") is not None:
                    result["reward_signal"] = data["reward_signal"]
                if data.get("latency_ms") is not None:
                    result["latency_ms"] = data["latency_ms"]
            elif step == "memory_lookup":
                if data.get("result"):
                    result["cache"] = data["result"]
            elif step == "evolution_check":
                if data.get("triggered") is not None:
                    result["evolution_triggered"] = data["triggered"]
            elif step == "task_normalization":
                meta = data.get("metadata", {})
                if meta.get("task_type"):
                    result["task_type"] = meta["task_type"]
                if meta.get("ambiguity_score") is not None:
                    result["ambiguity"] = meta["ambiguity_score"]
                if meta.get("small_model") is not None:
                    result["small_model"] = meta["small_model"]

        return result

    @staticmethod
    def what_if(
        execution_id: str,
        alternative_model: str,
    ) -> Optional[Dict[str, Any]]:
        summary = DecisionReplaySystem.summary(execution_id)
        if not summary:
            return None

        scores = summary.get("scores", {})
        original_model = summary.get("model", "?")
        original_reward = summary.get("reward_signal", 0)
        alt_score = scores.get(alternative_model, 0)
        orig_score = scores.get(original_model, 0)

        alt_reward = original_reward * (alt_score / orig_score) if orig_score > 0 else 0
        alt_reward = round(alt_reward, 2)

        return {
            "execution_id": execution_id,
            "original_model": original_model,
            "alternative_model": alternative_model,
            "original_score": orig_score,
            "alternative_score": alt_score,
            "original_reward": original_reward,
            "estimated_reward": alt_reward,
            "score_delta": round(alt_score - orig_score, 3),
            "would_be_better": alt_score > orig_score,
        }

    @staticmethod
    def compare(
        execution_id: str,
        model_a: str,
        model_b: str,
    ) -> Dict[str, Any]:
        a = DecisionReplaySystem.what_if(execution_id, model_a)
        b = DecisionReplaySystem.what_if(execution_id, model_b)

        if not a or not b:
            return {"error": "execution_id nao encontrado"}

        return {
            "execution_id": execution_id,
            "model_a": {"model": model_a, **a},
            "model_b": {"model": model_b, **b},
            "recommendation": model_a if a["estimated_reward"] > b["estimated_reward"] else model_b,
        }

    @staticmethod
    def train_bandit(
        execution_id: str,
        credit: CreditAssignmentEngine,
        node: str = "replay_train",
    ) -> Dict[str, Any]:
        rows = store.replay(execution_id)
        if not rows:
            return {"trained": False, "reason": "nenhum evento encontrado"}

        model = None
        reward = 0.5
        success = True
        latency = 0.0
        strategy = "general"

        for row in rows:
            data = row.get("_parsed") or {}
            step = data.get("step", "")

            if step == "model_selection":
                model = data.get("selected")
                strategy = data.get("metadata", {}).get("strategy", "general")
            elif step == "execution_metrics":
                reward = data.get("reward_signal", 0.5)
                latency = (data.get("latency_ms", 0) or 0) / 1000.0
                success = data.get("metadata", {}).get("success", True)

        if not model:
            return {"trained": False, "reason": "model_selection nao encontrado"}

        credit.record(ExecutionEvent(
            node=node,
            success=success,
            latency=latency,
            model=model,
            strategy=strategy,
        ))

        new_score = credit.score(node, model, strategy)

        return {
            "trained": True,
            "model": model,
            "reward": reward,
            "new_score": new_score,
            "strategy": strategy,
        }

    @staticmethod
    def explain(execution_id: str) -> Optional[Dict[str, Any]]:
        rows = store.replay(execution_id)
        if not rows:
            return None

        summary = DecisionReplaySystem.summary(execution_id)
        if not summary:
            return None

        trace_lines = []
        for row in rows:
            data = row.get("_parsed") or {}
            step = data.get("step", "?")
            ts = data.get("timestamp", "")[11:19] if data.get("timestamp") else ""
            tag = "; ".join(
                f"{k}={v}" for k, v in data.items()
                if k not in ("step", "timestamp", "execution_id", "metadata", "candidates")
                and v is not None
            )
            trace_lines.append(f"  [{ts}] {step}: {tag}")

        scores_str = ", ".join(
            f"{m}: {s}" for m, s in (summary.get("scores") or {}).items()
        )

        prompt = (
            "Você é um analista de sistemas especializado em pipelines de IA.\n"
            "Analise a execução abaixo e forneça um resumo em português claro e objetivo.\n"
            "Inclua: o que foi feito, qual modelo foi escolhido e por quê, "
            "se o cache foi usado, se houve exploração ou não, "
            "o desempenho (latência, recompensa), e se a evolução foi acionada.\n"
            "Mencione também quais alternativas foram consideradas.\n"
            "Mantenha o tom técnico mas acessível. Máximo 5 frases.\n\n"
            f"ID da execução: {execution_id}\n"
            f"Tipo de tarefa: {summary.get('task_type', '?')}\n"
            f"Ambiguidade: {summary.get('ambiguity', 0)}\n"
            f"Modelo pequeno: {summary.get('small_model', False)}\n"
            f"Cache: {summary.get('cache', '?')}\n"
            f"Modelo escolhido: {summary.get('model', '?')}\n"
            f"Scores dos candidatos: {scores_str}\n"
            f"Exploração: {summary.get('exploration', '?')}\n"
            f"Recompensa: {summary.get('reward_signal', '?')}\n"
            f"Latência: {summary.get('latency_ms', '?')}ms\n"
            f"Evolução acionada: {summary.get('evolution_triggered', '?')}\n\n"
            f"Traço completo:\n" + "\n".join(trace_lines[-10:]) + "\n\n"
            "Análise:"
        )

        try:
            from iaglobal.providers.provider_router import route_generate
            analysis = route_generate(
                model="auto",
                prompt=prompt,
                task_type="general",
            )
            analysis = (analysis or "").strip().strip("\"'")
        except Exception as e:
            analysis = f"[fallback] Execução {execution_id}: modelo {summary.get('model')}, recompensa {summary.get('reward_signal')}, latência {summary.get('latency_ms')}ms."

        return {
            "execution_id": execution_id,
            "analysis": analysis,
            "summary": summary,
        }
