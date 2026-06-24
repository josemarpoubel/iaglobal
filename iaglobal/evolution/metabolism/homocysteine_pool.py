"""HomocysteinePool — pool de skills candidatas (não validadas)."""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import time

from iaglobal._paths import HOMOCYSTEINE_POOL_FILE
from iaglobal.evolution.skills.skill import Skill
from iaglobal.evolution.skills.skill_registry import skill_registry

logger = logging.getLogger(__name__)

POOL_FILE = HOMOCYSTEINE_POOL_FILE


@dataclass
class CandidateSkill:
    skill: Skill
    generation: int = 0
    score: float = 0.0
    route: str = "undecided"
    source_gap: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_name": self.skill.name,
            "skill_description": self.skill.description,
            "generation": self.generation,
            "score": self.score,
            "route": self.route,
            "source_gap": self.source_gap,
            "created_at": round(self.created_at, 6),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateSkill":
        skill = Skill(
            name=data.get("skill_name", "unknown"),
            description=data.get("skill_description", ""),
            inputs=[],
            outputs=[],
            constraints=[],
            run_fn=None,
            version="1.0.0",
            tags=["candidate"],
        )
        return cls(
            skill=skill,
            generation=data.get("generation", 0),
            score=data.get("score", 0.0),
            route=data.get("route", "undecided"),
            source_gap=data.get("source_gap", ""),
        )


class HomocysteinePool:
    """Pool de skills candidatas aguardando decisão de rota."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or POOL_FILE
        self.candidates: List[CandidateSkill] = []
        self._io_lock = threading.Lock()
        self._load()

    def _load(self):
        with self._io_lock:
            try:
                if self.path.exists():
                    with open(self.path) as f:
                        data = json.load(f)
                        self.candidates = [CandidateSkill.from_dict(d) for d in data]
            except Exception as e:
                logger.debug("[HOMOCYSTEINE] Erro ao carregar: %s", e)

    def _save(self):
        with self._io_lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "w") as f:
                    json.dump([c.to_dict() for c in self.candidates], f, indent=2)
            except Exception as e:
                logger.debug("[HOMOCYSTEINE] Erro ao salvar: %s", e)

    def add(self, candidate: CandidateSkill):
        self.candidates.append(candidate)
        self._save()
        logger.info("[HOMOCYSTEINE] Candidate '%s' adicionada (score=%.2f)", candidate.skill.name, candidate.score)

    PROMOTION_THRESHOLD = 85

    def _promotion_threshold(self) -> float:
        scores = [c.score for c in self.candidates if isinstance(c.score, (int, float))]
        if scores and max(scores) <= 1.0:
            return 0.6
        return float(self.PROMOTION_THRESHOLD)

    def route_to_production(self, candidate: CandidateSkill) -> bool:
        try:
            promoted = Skill(
                name=candidate.skill.name,
                description=candidate.skill.description,
                inputs=list(candidate.skill.inputs),
                outputs=list(candidate.skill.outputs),
                constraints=list(candidate.skill.constraints),
                execution_policy=candidate.skill.execution_policy,
                run_fn=candidate.skill.run_fn,
                version=candidate.skill.version,
                tags=list(candidate.skill.tags),
                status="production",
            )
            skill_registry.register_or_update(promoted)
            candidate.route = "production"
            self._save()
            logger.info("[HOMOCYSTEINE] '%s' promovida a production (score=%.1f)", candidate.skill.name, candidate.score)
            return True
        except Exception as e:
            logger.warning("[HOMOCYSTEINE] Falha ao promover '%s': %s", candidate.skill.name, e)
            return False

    def route_to_guardrail(self, candidate: CandidateSkill) -> bool:
        try:
            guardrail_name = f"guardrail_{candidate.skill.name}"
            from iaglobal.evolution.skills.skill import Skill
            guardrail = Skill(
                name=guardrail_name,
                description=f"[GUARDRAIL] {candidate.skill.description}",
                inputs=["code"],
                outputs=["decision"],
                constraints=["deterministic", "fast"],
                run_fn=None,
                version="1.0.0",
                tags=["guardrail", "auto_generated"],
            )
            skill_registry.register_or_update(guardrail)
            candidate.route = "guardrail"
            self._save()
            logger.info("[HOMOCYSTEINE] '%s' → guardrail '%s'", candidate.skill.name, guardrail_name)
            return True
        except Exception as e:
            logger.warning("[HOMOCYSTEINE] Falha ao criar guardrail: %s", e)
            return False

    def get_pending(self) -> List[CandidateSkill]:
        return [c for c in self.candidates if c.route == "undecided"]

    def get_ready_for_methylation(self) -> List[CandidateSkill]:
        """Retorna candidatos com score >= threshold e rota indefinida.
        Chamado pelo no_evolution_homocysteine para estatísticas do pool."""
        threshold = self._promotion_threshold()
        return [c for c in self.candidates if c.route == "undecided" and c.score >= threshold]

    def get_candidates_for_methylation(self) -> List[CandidateSkill]:
        """Retorna os mesmos candidatos prontos para metilação.
        Chamado pelo no_evolution_methylation para processar a promoção."""
        return self.get_ready_for_methylation()

    def count(self) -> int:
        return len(self.candidates)


homocysteine_pool = HomocysteinePool()
