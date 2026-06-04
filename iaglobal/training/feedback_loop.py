# training/feedback_loop.py (Feedback loop for continuous learning and improvement)

import logging

from typing import Callable, Any, Dict, List, Optional
from ..memory.persistence import Persistence
from .._paths import DATA_DIR

logger = logging.getLogger(__name__)

class FeedbackLoop:
    """
    Gerencia o ciclo de vida do aprendizado contínuo.
    Persiste feedback para refinamento futuro e aciona ações de correção.
    """
    
    def __init__(self, storage: Persistence = None):
        self.persistence = storage or Persistence(storage_path=DATA_DIR)
        self.callbacks: List[Callable] = []
        # Carrega histórico existente para garantir persistência entre sessões
        self.feedback_history: List[Dict] = self.persistence.load_json("feedback_history") or []

    def register_callback(self, callback: Callable[[Dict], None]) -> None:
        """Registra funções que devem reagir a novos feedbacks (ex: disparar um re-treino)."""
        self.callbacks.append(callback)

    def add_feedback(self, task_id: str, feedback: str, score: float, agent_name: str = "unknown", metadata: Optional[Dict] = None) -> None:
        """
        Adiciona e persiste feedback sobre uma execução, vinculando ao agente responsável.
        """
        # Criamos o dicionário de metadados garantindo a inclusão do agente
        meta = metadata or {}
        meta['agent'] = agent_name
        
        feedback_item = {
            'task_id': task_id,
            'feedback': feedback,
            'score': score,
            'metadata': meta
        }
        
        self.feedback_history.append(feedback_item)
        
        # Persistência Atômica do histórico
        try:
            self.persistence.save_json("feedback_history", self.feedback_history)
            logger.info(f"✅ Feedback registrado: Agente={agent_name} | Score={score}")
        except Exception as e:
            logger.error(f"💥 Falha ao persistir feedback: {e}")

        self._trigger_callbacks(feedback_item)
    
    def _trigger_callbacks(self, feedback_item: Dict) -> None:
        for callback in self.callbacks:
            try:
                callback(feedback_item)
            except Exception as e:
                logger.error(f"Erro no callback de feedback: {e}")
    
    def get_performance_report(self) -> Dict[str, float]:
        """Gera métricas de desempenho para o módulo de reflexão."""
        if not self.feedback_history:
            return {"average_score": 0.0, "total_samples": 0}
            
        scores = [item['score'] for item in self.feedback_history]
        return {
            "average_score": sum(scores) / len(scores),
            "total_samples": len(scores),
            "critical_failures": len([s for s in scores if s < 0.3])
        }
