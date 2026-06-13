# iaglobal/agents/validator.py

"""SemanticValidator — Validação semântica e estrutural de código."""

import ast

from typing import Dict, Any, List

from iaglobal.validation.engine import FeedbackEngine

import logging

from iaglobal.utils.logger import logger

logger = logging.getLogger("ia-global")

class SemanticValidatorAgent:
    """Validador semântico — verifica código gerado pelo pipeline.

    Usado por:
    - builder.py: run_validator (via .validar())
    - multi_agent.py: fase critic_swarm (via .validate())
    """

    def __init__(self):
        self.engine = FeedbackEngine()

    def validar(self, task: str, code: str) -> Dict[str, Any]:
        """Valida código e retorna score + resultado.

        Args:
            task: descrição da tarefa (para contexto)
            code: código gerado

        Returns:
            dict com "score", "valid", "errors"
        """
        result = self.engine.validate(code)
        return {
            "score": result.score * 100,
            "valid": result.valid,
            "errors": result.errors,
            "decision": result.decision.value,
        }

    def validate(self, code: str, task: str = "") -> Dict[str, Any]:
        """Valida código — retorna resultado estruturado.

        Args:
            code: código a validar
            task: descrição da tarefa (opcional)

        Returns:
            dict com "valid" (bool) e "errors" (list)
        """
        result = self.engine.validate(code, {"retry_count": 0})
        return {
            "valid": result.valid,
            "errors": result.errors,
            "score": result.score,
        }


class SemanticValidator:
    """Validador semântico simplificado para o GateKeeper.

    Usado por:
    - builder.py: run_gatekeeper
    """

    def __init__(self):
        self.engine = FeedbackEngine()

    def validate(self, code: str, task: str = "") -> Dict[str, Any]:
        """Valida código — retorna dict com valid + errors."""
        result = self.engine.validate(code, {"retry_count": 0})
        return {
            "valid": result.valid,
            "errors": result.errors,
        }
