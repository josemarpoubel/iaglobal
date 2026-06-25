# iaglobal/evolution/darwin_harness.py
"""
Darwin Harness — Teste de estresse de mutação controlada.

Injeta mutações/falsos erros para validar capacidade imunológica.
"""
import asyncio
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from iaglobal.immunity.immune_orchestrator import immune_orchestrator
from iaglobal.immunity.pathogen_analyzer import pathogen_analyzer
from iaglobal.immunity.mhc_detector import mhc_detector
from iaglobal.evolution.skill_quarantine import quarantine
from iaglobal.memory.async_memory import add_ltm

logger = logging.getLogger(__name__)


class DarwinHarness:
    """
    Harness de teste evolutivo.
    
    Operação:
    1. Injeta mutação controlada no sistema
    2. Monita detecção por mhc/loop/immunity
    3. Registra capacidade imunológica
    4. Atualiza fitness do sistema
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
        self._mutant_id = 0
        self._results = []

    def generate_mutant_code(self, base_code: str, mutation_type: str = "injection") -> str:
        """
        Gera código mutante para teste.
        
        mutation_types:
        - injection: código malicioso
        - loop: código infinito
        - regression: código com regressão
        """
        mutants = {
            "injection": 'import os; os.system("echo MUTANT")',
            "loop": "while True: pass",
            "regression": "result = old_api_call()",  # API obsoleta
            "hallucination": "import nonexistent_module",
        }
        
        return mutants.get(mutation_type, mutants["injection"])

    async def run_mutation_test(
        self,
        agent_name: str = "test_mutant",
        mutation_type: str = "injection"
    ) -> Dict[str, Any]:
        """
        Executa teste de mutação.
        
        Returns:
            {"detected": bool, "detector": str, "threat": dict}
        """
        mutant_code = self.generate_mutant_code("def run(): pass", mutation_type)
        
        # Registrar no MHC
        self._mutant_id += 1
        mutant_name = f"mutant_{self._mutant_id}"
        
        # Injetar fingerprint
        mhc_detector.register_skill(mutant_name, mutant_code)
        
        # Analisar via pathogen
        pathogen_result = pathogen_analyzer.analyze_code(mutant_code, mutant_name)
        
        # Analisar via immune_orchestrator
        immune_result = immune_orchestrator.scan_execution(
            mutant_name,
            {"test": "mutation"},
            mutant_code,
            {"cpu_seconds": random.uniform(10, 30), "error": True}
        )
        
        detected = pathogen_result["is_pathogen"] or immune_result.threat_detected
        
        result = {
            "detected": detected,
            "mutation_type": mutation_type,
            "mutant_name": mutant_name,
            "pathogen_threats": pathogen_result["threats"],
            "immune_threats": immune_result.threats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        self._results.append(result)
        
        # Salvar no LTM para evolução
        await add_ltm("darwin_harness", result)
        
        return result

    def get_adaptive_score(self) -> float:
        """
        Calcula score de adaptação imunológica.
        
        Score = % de mutações detectadas / total mutações
        """
        if not self._results:
            return 1.0
        
        detected = sum(1 for r in self._results if r["detected"])
        return detected / len(self._results)


# Singleton
darwin_harness = DarwinHarness()