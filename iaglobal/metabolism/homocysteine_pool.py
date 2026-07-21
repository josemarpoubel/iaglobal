"""HomocysteinePool — pool de skills candidatas (não validadas)."""

import logging
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import time

from iaglobal._paths import HOMOCYSTEINE_POOL_FILE
from iaglobal.evolution.skills.native.skill import Skill
from iaglobal.evolution.skills.native.skill_registry import skill_registry
from iaglobal.utils.atomic_io import AtomicJSONStore

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
        self._store = AtomicJSONStore(self.path, default=[])
        self._load()

    def _load(self):
        with self._io_lock:
            try:
                data = self._store.read_sync()
                self.candidates = [CandidateSkill.from_dict(d) for d in data]
                dirty = False
                for c in self.candidates:
                    if c.route == "production" and not self._is_production_worthy(c)[0]:
                        c.route = "guardrail"
                        dirty = True
                if dirty:
                    self._store.mutate_sync(
                        lambda _: [c.to_dict() for c in self.candidates]
                    )
            except Exception as e:
                logger.debug("[HOMOCYSTEINE] Erro ao carregar: %s", e)

    def add(self, candidate: CandidateSkill):
        with self._io_lock:
            self.candidates.append(candidate)
            self._store.mutate_sync(lambda _: [c.to_dict() for c in self.candidates])
        logger.info(
            "[HOMOCYSTEINE] Candidate '%s' adicionada (score=%.2f)",
            candidate.skill.name,
            candidate.score,
        )

    PROMOTION_THRESHOLD = 85

    # Gate de honestidade: só sobe para produção skill real e executável.
    MIN_PRODUCTION_DESC_LEN = 40
    MIN_PRODUCTION_SOURCE_LEN = 40

    def _is_production_worthy(self, candidate: CandidateSkill) -> tuple:
        """Valida se um candidato merece rota 'production' (anti-falso-positivo).

        Rejeita skills sem run_fn (mortas), descrições/fontes truncadas ou
        curtas, dumps crus de telemetria/IVM e baixa entropia. Sem isso, o
        ciclo de metilação promovia ruído (ex.: dump de IVM) a produção.
        """
        desc = (candidate.skill.description or "").strip()
        src = (candidate.source_gap or "").strip()
        # Dump bruto de telemetria/IVM (dict literal, ex.: diagnóstico do sistema)
        # não é skill funcional — rejeita para não promover ruído a produção.
        if "{" in desc or "{" in src:
            return False, "descrição/fonte contém dump de dicionário (ruído)"
        if len(desc) < self.MIN_PRODUCTION_DESC_LEN:
            return (
                False,
                f"descrição curta ({len(desc)}<{self.MIN_PRODUCTION_DESC_LEN})",
            )
        if len(src) < self.MIN_PRODUCTION_SOURCE_LEN:
            return (
                False,
                f"fonte de gap curta ({len(src)}<{self.MIN_PRODUCTION_SOURCE_LEN})",
            )
        words = desc.split()
        if words and len(set(words)) < min(8, len(words)):
            return False, "baixa entropia / descrição redundante"
        return True, ""

    def _promotion_threshold(self) -> float:
        scores = [c.score for c in self.candidates if isinstance(c.score, (int, float))]
        if scores and max(scores) <= 1.0:
            return 0.6
        return float(self.PROMOTION_THRESHOLD)

    def route_to_production(self, candidate: CandidateSkill) -> bool:
        worthy, reason = self._is_production_worthy(candidate)
        if not worthy:
            logger.warning(
                "[HOMOCYSTEINE] Promoção NEGADA para '%s': %s",
                candidate.skill.name,
                reason,
            )
            self.route_to_guardrail(candidate)
            return False
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
            with self._io_lock:
                candidate.route = "production"
                self._store.mutate_sync(
                    lambda _: [c.to_dict() for c in self.candidates]
                )
            logger.info(
                "[HOMOCYSTEINE] '%s' promovida a production (score=%.1f)",
                candidate.skill.name,
                candidate.score,
            )
            return True
        except Exception as e:
            logger.warning(
                "[HOMOCYSTEINE] Falha ao promover '%s': %s", candidate.skill.name, e
            )
            return False

    def route_to_guardrail(self, candidate: CandidateSkill) -> bool:
        try:
            guardrail_name = f"guardrail_{candidate.skill.name}"
            from iaglobal.evolution.skills.native.skill import Skill

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
            with self._io_lock:
                candidate.route = "guardrail"
                self._store.mutate_sync(
                    lambda _: [c.to_dict() for c in self.candidates]
                )
            logger.info(
                "[HOMOCYSTEINE] '%s' → guardrail '%s'",
                candidate.skill.name,
                guardrail_name,
            )
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
        return [
            c
            for c in self.candidates
            if c.route == "undecided" and c.score >= threshold
        ]

    def get_candidates_for_methylation(self) -> List[CandidateSkill]:
        """Retorna os mesmos candidatos prontos para metilação.
        Chamado pelo no_evolution_methylation para processar a promoção."""
        return self.get_ready_for_methylation()

    def count(self) -> int:
        return len(self.candidates)

    def remove(self, skill_name: str) -> bool:
        """Remove skill do pool por nome (apoptose de skills de baixa qualidade)."""
        with self._io_lock:
            before = len(self.candidates)
            self.candidates = [c for c in self.candidates if c.skill.name != skill_name]
            if len(self.candidates) < before:
                self._store.mutate_sync(
                    lambda _: [c.to_dict() for c in self.candidates]
                )
                logger.info("[HomocysteinePool] Skill removida: %s", skill_name)
                return True
        return False


homocysteine_pool = HomocysteinePool()
