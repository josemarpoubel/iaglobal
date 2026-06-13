# iaglobal/graphs/node_result.py

"""Contrato de saída para nós do pipeline."""

from dataclasses import dataclass, field
from typing import Any, Optional

import logging

from iaglobal.utils.logger import logger

logger = logging.getLogger("ia-global")

@dataclass
class NodeResult:
    """Resultado padrão de execução de um nó com instrumentação de log."""
    success: bool = False
    output: Any = None
    error: Optional[str] = None
    score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """Loga automaticamente a criação do resultado."""
        if self.success:
            logger.debug(f"✅ [NODE_RESULT] Nó executado com sucesso. Score: {self.score}")
        else:
            logger.error(f"❌ [NODE_RESULT] Nó falhou. Erro: {self.error}")

    def log_summary(self, node_name: str):
        """Loga um resumo estruturado da execução do nó."""
        status = "SUCESSO" if self.success else "FALHA"
        logger.info(
            f"📊 [NODE_RESULT] Resumo - Nó: {node_name} | Status: {status} | "
            f"Score: {self.score} | Erro: {self.error or 'Nenhum'}"
        )

    def to_dict(self):
        """Converte para dicionário para facilitar persistência no DB."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "score": self.score,
            "metadata": self.metadata
        }
