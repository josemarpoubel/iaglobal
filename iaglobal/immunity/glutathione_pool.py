"""GlutathionePool — pool de skills de proteção com ImmuneResponse."""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path
import json

from iaglobal._paths import GLUTATHIONE_POOL_FILE
from iaglobal.evolution.skills.skill_registry import skill_registry

logger = logging.getLogger(__name__)

POOL_FILE = GLUTATHIONE_POOL_FILE


class ImmuneResponse(Enum):
    ISOLATE = "isolate"
    CORRECT = "correct"
    ESCALATE = "escalate"


class GlutathionePool:
    """Pool de guardrails e respostas imunes."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or POOL_FILE
        self.guardrails: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        try:
            if self.path.exists():
                with open(self.path) as f:
                    self.guardrails = json.load(f)
        except Exception as e:
            logger.debug("[GLUTATHIONE] Erro ao carregar: %s", e)

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.guardrails, f, indent=2)
        except Exception as e:
            logger.debug("[GLUTATHIONE] Erro ao salvar: %s", e)

    def add_guardrail(self, name: str, description: str, detector: str):
        self.guardrails.append({
            "name": name,
            "description": description,
            "detector": detector,
        })
        self._save()

    def respond(self, threat_type: str, threat_data: Dict[str, Any]) -> Dict[str, Any]:
        if threat_type == "loop":
            self.add_guardrail(
                name=f"guardrail_loop_{threat_data.get('node', 'unknown')}",
                description=f"Isolamento automático de nó em loop",
                detector="loop_detector",
            )
            return {
                "response": ImmuneResponse.ISOLATE.value,
                "action": f"Nó '{threat_data.get('node')}' em loop — isolando",
                "guardrails_applied": 1,
            }

        if threat_type == "regression":
            self.add_guardrail(
                name=f"guardrail_regression_{threat_data.get('node', 'unknown')}",
                description=f"Correção automática de regressão",
                detector="regression_detector",
            )
            return {
                "response": ImmuneResponse.CORRECT.value,
                "action": f"Regressão em '{threat_data.get('node')}' — aplicando correção",
                "guardrails_applied": 1,
            }

        if threat_type == "hallucination":
            self.add_guardrail(
                name=f"guardrail_hallucination_{hash(str(threat_data.get('issues', ''))) % 10000:04d}",
                description=f"Escalamento de alucinação detectada",
                detector="hallucination_detector",
            )
            return {
                "response": ImmuneResponse.ESCALATE.value,
                "action": f"Alucinação detectada — escalando",
                "guardrails_applied": 1,
            }

        return {"response": ImmuneResponse.ESCALATE.value, "action": "Tipo desconhecido — escalando", "guardrails_applied": 0}

    def count(self) -> int:
        return len(self.guardrails)
