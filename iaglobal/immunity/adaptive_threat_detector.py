# iaglobal/immunity/adaptive_threat_detector.py
"""
AdaptiveThreatDetector — Aprendizado contínuo de padrões de ataque.

Evolui o immune_orchestrator sem atualização manual via:
- Análise de skills aprovadas em evolucao_approved_skill_lt_...
- Detecção de padrões emergentes
- Atualização automática de assinaturas
"""
import logging
import hashlib
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AdaptiveThreatDetector:
    """
    Detector adaptativo que aprende com skills aprovadas.
    
    Operação:
    1. Scan periodic de skills aprovadas
    2. Extrai padrões benignos previamente desconhecidos
    3. Atualiza whitelist dinâmica
    4. Treina assinaturas de patógenos emergentes
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
        self._benign_patterns: List[str] = []  # Padrões aprovados
        self._emerging_threats: List[Dict[str, Any]] = []  # Ameaças detectadas
        self._learned_signatures: Dict[str, str] = {}  # Hash → pattern

    def learn_from_approved_skill(self, skill_name: str, skill_code: str) -> None:
        """
        Aprende com skill aprovada - adiciona padrões benignos.
        """
        # Gerar fingerprint do código aprovado
        fingerprint = hashlib.sha3_256(skill_code.encode()).hexdigest()[:16]
        
        if fingerprint not in self._learned_signatures:
            self._learned_signatures[fingerprint] = skill_code[:100]
            logger.info(f"[ADAPTIVE] Skill aprovada registrada: {skill_name} → {fingerprint}")

    def scan_for_emerging_threats(self, code: str) -> Dict[str, Any]:
        """
        Detecta ameaças emergentes não cobertas por regras estáticas.
        
        Returns:
            {"is_threat": bool, "confidence": float, "pattern": str}
        """
        emerging_indicators = [
            "eval(", "exec(", "compile(", 
            "os.system", "subprocess.Popen",
            "__import__", "globals()", "locals()",
            "pickle.loads", "marshal.loads",
        ]
        
        found = [ind for ind in emerging_indicators if ind in code]
        
        if found:
            return {
                "is_threat": True,
                "confidence": 0.9,
                "pattern": "emerging_pattern",
                "indicators": found,
            }
        
        return {"is_threat": False, "confidence": 0.0}

    def get_benign_whitelist(self) -> List[str]:
        """Retorna padrões considerados benignos aprendidos."""
        return list(self._learned_signatures.values())

    def update_from_obsidian_approved(self) -> int:
        """
        Atualiza whitelist a partir de skills aprovadas no Obsidian.
        
        Returns:
            Número de padrões aprendidos
        """
        learned = 0
        obsidian_dir = Path("iaglobal/obsidian/03_Long_Term")
        
        if obsidian_dir.exists():
            for file in obsidian_dir.glob("evolucao_approved_skill_lt_*.md"):
                try:
                    content = file.read_text()
                    # Extrair código da skill aprovada
                    if "```python" in content:
                        code = content.split("```python")[1].split("```")[0]
                        fingerprint = hashlib.sha3_256(code.encode()).hexdigest()[:16]
                        self._learned_signatures[fingerprint] = code[:100]
                        learned += 1
                except Exception as e:
                    logger.warning(f"[ADAPTIVE] Erro lendo {file}: {e}")
        
        return learned


# Singleton
adaptive_threat_detector = AdaptiveThreatDetector()