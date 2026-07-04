# iaglobal/events/replay.py

# iaglobal/events/replay.py

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
    def batch_compare_what_if(
        execution_ids: List[str],
        alternative_model: str
    ) -> Dict[str, Any]:
        """
        Compara o resultado hipotético (what_if) para uma lista de execuções.
        Útil para identificar se um modelo alternativo seria consistentemente 
        melhor que os modelos originais em um lote de tarefas.
        """
        results = {}
        total_better = 0
        
        for eid in execution_ids:
            res = DecisionReplaySystem.what_if(eid, alternative_model)
            if res:
                results[eid] = res
                if res.get("would_be_better", False):
                    total_better += 1
        
        # Estatísticas agregadas do lote
        avg_delta = sum(r.get("score_delta", 0) for r in results.values()) / len(results) if results else 0
        
        return {
            "model_tested": alternative_model,
            "total_processed": len(results),
            "better_in_count": total_better,
            "consistency_score": total_better / len(results) if results else 0,
            "average_score_improvement": round(avg_delta, 3),
            "details": results
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

        # 1. Instancia o Bandit que centraliza as regras da política
        bandit = BanditPolicy(credit=credit)

        # 2. Em vez de chamar o credit diretamente, avisa o bandit que um evento ocorreu
        bandit.update_policy(
            node=node,
            model=model,
            strategy=strategy,
            success=success,
            latency=latency,
            reward=reward # Se sua lógica de score usar o reward futuramente
        )

        # 3. Consulta o novo score atualizado através do bandit
        new_score = credit.score(node, model, strategy)

        return {
            "trained": True,
            "model": model,
            "reward": reward,
            "new_score": new_score,
            "strategy": strategy,
        }

    @staticmethod
    def explain(
        execution_id: str, 
        credit: CreditAssignmentEngine  # Injetando o motor de créditos necessário para o Bandit
    ) -> Optional[Dict[str, Any]]:
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
            "### Papel\n"
            "Você é um Engenheiro de IA Sênior especializado em observabilidade de pipelines. "
            "Sua função é realizar um 'post-mortem' técnico rápido e preciso de uma execução de pipeline.\n\n"
            
            "### Instruções de Análise\n"
            "1. Sintetize a execução em português técnico, porém acessível.\n"
            "2. Justifique a escolha do modelo com base nos scores e na ambiguidade.\n"
            "3. Avalie se o trade-off entre latência e performance foi satisfatório.\n"
            "4. Se a evolução foi acionada, indique o motivo crítico.\n"
            "5. Use o formato: [Resumo Geral] -> [Análise de Decisão] -> [Impacto de Performance].\n"
            "6. **Limite estritamente a 5 frases.**\n\n"
            
            "### Dados da Execução\n"
            f"- ID: {execution_id} | Tipo: {summary.get('task_type', '?')}\n"
            f"- Ambiguidade: {summary.get('ambiguity', 0)} | Cache: {summary.get('cache', '?')}\n"
            f"- Modelo Escolhido: {summary.get('model', '?')} (Small Model: {summary.get('small_model', False)})\n"
            f"- Performance: Latência {summary.get('latency_ms', '?')}ms | Recompensa: {summary.get('reward_signal', '?')}\n"
            f"- Exploração: {summary.get('exploration', '?')} | Evolução Acionada: {summary.get('evolution_triggered', '?')}\n"
            f"- Scores Candidatos: {scores_str}\n\n"
            
            "### Últimos 10 passos do Log (Contexto de Decisão)\n"
            f"{chr(10).join(trace_lines[-10:])}\n\n"
            
            "Análise Técnica:"
        )

        try:
            # 1. Instancia o Bandit localmente usando o motor de créditos recebido
            bandit = BanditPolicy(credit=credit)

            # 2. Pergunta ao bandit qual string de modelo usar baseada no histórico
            chosen_model = bandit.select_model(
                node="analisador", 
                strategy="general"
            )

            # 3. Executa através da interface limpa e encapsulada do bandit
            analysis = bandit.execute_model(
                model=chosen_model,
                prompt=prompt,
                task_type="general"
            )
            analysis = (analysis or "").strip().strip("\"'")
            
        except Exception as e:
            logger.error(f"[REPLAY] Falha ao processar explicação técnica: {e}")
            failed_model = summary.get('model') or (locals().get('chosen_model') or "desconhecido")
            analysis = f"[fallback] Execução {execution_id}: modelo {failed_model}, recompensa {summary.get('reward_signal')}, latência {summary.get('latency_ms')}ms."

        return {
            "execution_id": execution_id,
            "analysis": analysis,
            "summary": summary,
        }

