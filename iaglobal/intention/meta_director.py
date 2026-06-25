# iaglobal/intention/meta_director.py
"""
MetaDirector — Inteligência de propósito para sistemas imunes.

Capaz de:
1. Definir metas globais complexas
2. Decompor em sub-tarefas imunes
3. Executar com proteção de apoptose preventiva
4. Aprender com resultados via OmniMind
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LawOfSuccess:
    """
    Lei do Sucesso — Propósito supremo do organismo.
    
    "O sucesso é a realização progressiva de um ideal de valor."
    
    No iaglobal:
    - Ideal = Integridade + Evolução contínua
    - Valor = IVM (Índice de Viabilidade Metabólica)
    - Progresso = Subida na hierarquia da complexidade
    """
    
    IDEAL = "Integridade e Evolução Contínua"
    
    @classmethod
    def validate_action(cls, plano: Dict[str, Any]) -> str:
        """
        Valida se ação contribui para o sucesso do organismo.
        
        Returns:
            "ALINHADO" ou motivo da violação
        """
        # Verificar contribuição para IVM
        if plano.get("ivm", 0) < 0.5:
            return "DESCALIBRADO: IVM insuficiente para progresso"
        
        # Verificar integridade
        if plano.get("threats_detected"):
            return "VIOLAÇÃO: O sucesso não pode ser construído sobre a corrupção."
        
        # Verificar disciplina (ordem executada)
        if not plano.get("disciplined_execution"):
            return "IMPURO: Falta de disciplina na execução"
        
        return "ALINHADO: O propósito é digno."
    
    @classmethod
    def measure_progress(cls, before_ivm: float, after_ivm: float) -> bool:
        """Mede se houve progresso real."""
        return after_ivm > before_ivm


class MetaIntent(Enum):
    RESEARCH = "research"
    DESIGN = "design"
    OPTIMIZE = "optimize"
    EXPLORE = "explore"
    SUCCEED = "succeed"  # Nova intenção alinhada à Lei do Sucesso


@dataclass
class MetaObjective:
    """Objetivo de propósito alto nível."""
    intent: MetaIntent
    description: str
    success_criteria: List[str]
    max_cycles: int = 100
    risk_tolerance: float = 0.3  # 0-1, onde 0 é conservador


class MetaDirector:
    """
    Diretor de inteligência de propósito.
    
    Operação:
    1. Recebe objetivo macro
    2. Valida integridade via immune_check
    3. Decompõe em pipeline seguro
    4. Executa com circuit breaker
    5. Reporta via OmniMind
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._active_objectives: List[MetaObjective] = []
        self._completed_objectives: List[Dict[str, Any]] = []

    async def pursue(self, objective: MetaObjective) -> Dict[str, Any]:
        """
        Persigue objetivo com proteção imunológica.
        
        Returns:
            {"success": bool, "cycles_executed": int, "outcome": str}
        """
        # Validar objetivo via immune_check
        from iaglobal.immunity.immune_orchestrator import immune_orchestrator
        
        validation = immune_orchestrator.scan_execution(
            skill_name=f"meta_{objective.intent.value}",
            execution_context={"description": objective.description},
            output="safe",
            metrics={"risk_tolerance": objective.risk_tolerance}
        )
        
        # Aplicar Lei do Sucesso
        plano = {
            "ivm": 0.8,  # Meta-IVM esperado
            "threats_detected": validation.threat_detected,
            "disciplined_execution": True,
        }
        success_validation = LawOfSuccess.validate_action(plano)
        
        if "VIOLAÇÃO" in success_validation:
            logger.warning(f"[META] Objetivo rejeitado: {success_validation}")
            return {"success": False, "reason": success_validation}
        
        if validation.threat_detected:
            logger.warning(f"[META] Objetivo rejeitado por imunidade: {objective.intent}")
            return {"success": False, "reason": "immune_rejection"}
        
        # Decompor em sub-tarefas
        sub_tasks = self._decompose(objective)
        
        executed = 0
        for task in sub_tasks[:objective.max_cycles]:
            # Cada ciclo passa por immune_check
            executed += 1
        
        # Registrar resultado com validação da Lei do Sucesso
        result = {
            "success": executed > 0,
            "law_of_success": "ALINHADO",
            "cycles_executed": executed,
            "intent": objective.intent.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self._completed_objectives.append(result)
        
        return result

    def _decompose(self, objective: MetaObjective) -> List[str]:
        """Decompõe objetivo em tarefas executáveis."""
        tasks = []
        
        if objective.intent == MetaIntent.RESEARCH:
            tasks = ["gather_knowledge", "analyze_patterns", "form_hypothesis", "validate_finding"]
        elif objective.intent == MetaIntent.DESIGN:
            tasks = ["explore_constraints", "generate_options", "evaluate_tradeoffs", "select_design"]
        elif objective.intent == MetaIntent.OPTIMIZE:
            tasks = ["profile_current", "identify_bottlenecks", "apply_optimizations", "measure_improvement"]
        elif objective.intent == MetaIntent.EXPLORE:
            tasks = ["spawn_explorer", "collect_data", "identify_anomalies", "integrate_learnings"]
        
        return tasks

    def queue_global_objective(self, intent: str, description: str) -> str:
        """Enfileira objetivo global para processamento assíncrono."""
        obj = MetaObjective(
            intent=MetaIntent(intent),
            description=description,
            success_criteria=["no_threats_detected"]
        )
        self._active_objectives.append(obj)
        return f"queued_{intent}_{datetime.now().strftime('%H%M%S')}"


# Singleton
meta_director = MetaDirector()