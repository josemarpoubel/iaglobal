# iaglobal/evolution/reward_aggregator.py

import os
import logging
from typing import Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Limites dinâmicos configuráveis via Infraestrutura como Código (IaC) ou .env
LATENCY_THRESHOLD_LOW = float(os.getenv("REWARD_LATENCY_THRESHOLD_LOW", "2000.0"))
LATENCY_THRESHOLD_HIGH = float(os.getenv("REWARD_LATENCY_THRESHOLD_HIGH", "5000.0"))
COST_THRESHOLD_LOW = float(os.getenv("REWARD_COST_THRESHOLD_LOW", "0.001"))
COST_THRESHOLD_HIGH = float(os.getenv("REWARD_COST_THRESHOLD_HIGH", "0.01"))


@dataclass(frozen=True)
class RewardMetrics:
    """Métricas imutáveis de uma execução para cálculo analítico de recompensa."""
    success: bool = False
    latency_ms: float = 5000.0
    cost_usd: float = 0.0
    token_count: int = 0
    error_type: Optional[str] = None  # "timeout", "http_402", "http_429", "http_500", etc.


class RewardAggregator:
    """
    Calcula e agrega recompensas para o aprendizado contínuo (Bandit / Credit Assignment).
    Equilibra a eficácia (sucesso) com a eficiência operacional (latência e custo).
    """

    def calculate_reward(self, metrics: RewardMetrics) -> float:
        """
        Calcula a recompensa escalar baseada nas métricas operacionais recebidas.
        Garante limites matemáticos estáveis entre [-1.0, 2.0].
        """
        reward = 0.0

        if metrics.success:
            reward += 1.0
            
            # Bónus incremental por velocidade operacional
            if metrics.latency_ms < 500.0:
                reward += 0.3
            elif metrics.latency_ms < LATENCY_THRESHOLD_LOW:
                reward += 0.1
                
            # Bónus incremental por eficiência financeira (custo)
            if metrics.cost_usd < COST_THRESHOLD_LOW:
                reward += 0.2
            elif metrics.cost_usd < COST_THRESHOLD_HIGH:
                reward += 0.1
        else:
            # Penalidade base severa por quebra de contrato de execução
            reward -= 0.5

            # Penalizações granulares baseadas na tipagem do erro
            if metrics.error_type:
                err = metrics.error_type.lower()
                if "timeout" in err:
                    reward -= 0.5
                elif "429" in err or "http_4" in err:
                    reward -= 0.3  # Rate limit ou erros de requisição
                elif "500" in err or "http_5" in err:
                    reward -= 0.4  # Falhas internas do provedor de LLM

            # Penalidades progressivas por degradação de tempo de resposta (latência)
            if metrics.latency_ms > LATENCY_THRESHOLD_LOW:
                reward -= 0.2
            if metrics.latency_ms > LATENCY_THRESHOLD_HIGH:
                reward -= 0.3

        # 🔥 Proteção de Hiperparâmetro: Normalização estrita para estabilidade do Bandit
        return max(-1.0, min(2.0, reward))

    def record_reward(self, credit: Any, node: str, model: str, strategy: str, reward: float, actual_success: bool):
        """
        Envia de forma correta e sem efeitos colaterais a recompensa ao CreditAssignmentEngine.
        """
        try:
            from iaglobal.graphs.telemetry import ExecutionEvent
            
            # NOTA DE ENGENHARIA: Certifique-se de que a classe ExecutionEvent aceita o parâmetro custom_reward
            # Se a classe ExecutionEvent do seu core não possuir este campo, utilize o dicionário de metadados internos (metadata/tags)
            event = ExecutionEvent(
                node=node,
                success=actual_success,  # 🔥 CORREÇÃO: Sucesso real e fidedigno, independente da nota da reward
                latency=0.0,  # Zera ou passa a latência real se disponível, nunca o valor mascarado da recompensa
                model=model,
                strategy=strategy,
            )
            
            # Injeta de forma explícita e segura a recompensa via atributo dinâmico ou dicionário interno
            if hasattr(event, "metadata") and isinstance(event.metadata, dict):
                event.metadata["evolution_reward"] = reward
            else:
                object.__setattr__(event, "evolution_reward", reward) if hasattr(event, "__frozen__") else setattr(event, "evolution_reward", reward)

            credit.record(event)
            logger.debug("[REWARD-AGGREGATOR] Recompensa de %.2f gravada com sucesso para o nó '%s'", reward, node)
            
        except Exception as e:
            logger.error("[REWARD-AGGREGATOR] Falha crítica ao registar recompensa no motor de crédito: %s", e)


# Instância global singleton do barramento
reward_aggregator = RewardAggregator()
