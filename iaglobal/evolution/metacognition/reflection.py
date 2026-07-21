# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# iaglobal/evolution/metacognition/reflection.py
"""
ReflectionMemory — Metacognição: produz conhecimento SOBRE o sistema.

DIFERENTE de memória (que recupera conhecimento DO sistema), reflection
é um processo ativo de inspeção e auto-avaliação.

Contém:
    - Reflexões do CriticAgent sobre execuções
    - Insights de verificações arquiteturais
    - Lições de auditorias
    - Reflexões sobre gaps de conhecimento
    - Análises de desempenho e otimizações sugeridas

Características:
    - Gerada internamente (não por LLM externo)
    - Usada para evolução heurística
    - Alimenta loops de reflexão
    - É metacognição, não memória
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Reflection:
    """
    Registro de reflexão do sistema.

    Uma reflexão é um INSIGHT gerado pelo sistema sobre seu próprio funcionamento.
    Não é uma memória recuperada — é conhecimento produzido internamente.
    """

    execution_id: str
    agent_id: str
    insight: str
    category: str = "general"  # architecture, performance, security, learning
    confidence: float = 1.0
    action_suggested: Optional[str] = None
    tags: tuple = ()

    @property
    def is_empty(self) -> bool:
        return not self.insight or not self.insight.strip()


class ReflectionEngine:
    """
    Motor de reflexão — produz metacognição a partir de execuções.

    Usado para:
        - Avaliar qualidade de execuções passadas
        - Identificar gaps de conhecimento
        - Sugerir melhorias arquiteturais
        - Aprender com falhas
    """

    def __init__(self):
        pass

    def reflect_on_execution(
        self,
        execution_id: str,
        agent_id: str,
        outcome: str,
        errors: list = None,
    ) -> Reflection:
        """
        Gera uma reflexão sobre uma execução.

        Args:
            execution_id: ID da execução
            agent_id: Agente que executou
            outcome: Resultado (success, failure, partial)
            errors: Lista de erros encontrados

        Returns:
            Reflection com insight sobre a execução
        """
        if errors:
            insight = f"Falhas detectadas em {agent_id}: {'; '.join(errors)}"
            category = "learning"
            action = "review_and_fix"
        elif outcome == "success":
            insight = f"Execução {agent_id} bem-sucedida"
            category = "performance"
            action = None
        else:
            insight = f"Execução {agent_id} com resultado parcial"
            category = "general"
            action = None

        return Reflection(
            execution_id=execution_id,
            agent_id=agent_id,
            insight=insight,
            category=category,
            action_suggested=action,
        )
