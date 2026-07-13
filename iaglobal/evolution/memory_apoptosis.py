# iaglobal/evolution/memory_apoptosis.py
"""
MemoryApoptosis — Filtro de Qualidade Metabólica para Skills e Buscas.

Remove skills e memórias que não foram reutilizadas após N ciclos,
evitando poluição do EpigeneticRegistry e Obsidian.

Analogia biológica:
  - Sinapses não usadas → podadas (synaptic pruning)
  - Células não funcionais → apoptose
  - Memórias de curto prazo não consolidadas → esquecidas

Métricas de qualidade:
  1. Reuso count (quantas vezes a skill foi usada)
  2. Success rate (taxa de sucesso quando usada)
  3. Recency (quando foi usada pela última vez)
  4. Bandit score (IVM médio quando executada)
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.memory_apoptosis")


@dataclass
class ApoptosisCriteria:
    """Critérios para apoptose de memória/skill."""

    max_age_days: float = 7.0  # Idade máxima em dias
    min_reuse_count: int = 3  # Mínimo de reusos para sobreviver
    min_success_rate: float = 0.5  # Taxa mínima de sucesso (50%)
    max_idle_cycles: int = 10  # Máximo de ciclos sem uso
    min_critic_score: float = 0.4  # Nota mínima do Critic (0..1)

    # Pesos para scoring
    weight_age: float = 0.2
    weight_reuse: float = 0.3
    weight_success: float = 0.2
    weight_critic: float = 0.3  # Critic tem peso alto!


@dataclass
class MetabolicHealth:
    """Saúde metabólica de uma skill/memória."""

    skill_id: str
    age_days: float
    reuse_count: int
    success_rate: float
    idle_cycles: int
    bandit_ivm: float
    critic_score: float = 0.5  # Nota do Critic (novo!)

    # Score calculado (0..1)
    health_score: float = 0.0

    # Decisão
    should_apoptose: bool = False
    apoptosis_reason: str = ""
    is_pathogenic: bool = False  # Se é "doente" (critic baixo)
    is_zombie: bool = False  # Se é "zumbi" (sem uso)


class MemoryApoptosis:
    """
    Gerencia apoptose de skills e memórias baseado em qualidade metabólica.

    Uso:
      apoptosis = MemoryApoptosis()
      await apoptosis.evaluate_and_prune()
    """

    def __init__(self, criteria: ApoptosisCriteria = None):
        self.criteria = criteria or ApoptosisCriteria()
        self.apoptosis_log: List[Dict] = []

    async def evaluate_and_prune(self) -> Dict:
        """
        Avalia todas as skills e memórias, remove as de baixa qualidade.

        Returns:
            dict com:
                - evaluated: quantas skills avaliadas
                - pruned: quantas skills removidas
                - saved: quantas skills mantidas
                - health_improvement: ganho de eficiência estimado
        """
        logger.info("🧬 [Apoptosis] Iniciando avaliação de qualidade metabólica...")

        result = {
            "evaluated": 0,
            "pruned": 0,
            "saved": 0,
            "health_improvement": 0.0,
            "apoptosed_skills": [],
        }

        # 1. Avalia skills no HomocysteinePool
        try:
            from iaglobal.metabolism.homocysteine_pool import homocysteine_pool

            # Pega todas as skills pending
            skills = homocysteine_pool.get_pending()

            skills_to_remove = []

            for skill in skills:
                result["evaluated"] += 1

                # Calcula saúde metabólica
                health = await self._calculate_metabolic_health(skill)

                if health.should_apoptose:
                    # Marca para remoção
                    if health.is_pathogenic:
                        logger.error(
                            "🦠 [Apoptosis] Skill PATOGÊNICA removida: %s | critic=%.2f | health=%.2f",
                            skill.skill.name,
                            health.critic_score,
                            health.health_score,
                        )
                    elif health.is_zombie:
                        logger.warning(
                            "🧟 [Apoptosis] Skill ZUMBI removida: %s | age=%.1fd | reuses=%d",
                            skill.skill.name,
                            health.age_days,
                            health.reuse_count,
                        )
                    else:
                        logger.warning(
                            "❌ [Apoptosis] Skill removida: %s | reason=%s | health=%.2f",
                            skill.skill.name,
                            health.apoptosis_reason,
                            health.health_score,
                        )

                    skills_to_remove.append(skill)
                    result["pruned"] += 1
                    result["apoptosed_skills"].append(
                        {
                            "name": skill.skill.name,
                            "reason": health.apoptosis_reason,
                            "health_score": health.health_score,
                            "critic_score": health.critic_score,
                            "is_pathogenic": health.is_pathogenic,
                            "is_zombie": health.is_zombie,
                        }
                    )

                    # Log para apoptose engine
                    self.apoptosis_log.append(
                        {
                            "timestamp": time.time(),
                            "skill_id": skill.skill.name,
                            "reason": health.apoptosis_reason,
                            "metrics": {
                                "age_days": health.age_days,
                                "reuse_count": health.reuse_count,
                                "success_rate": health.success_rate,
                                "idle_cycles": health.idle_cycles,
                            },
                        }
                    )
                else:
                    result["saved"] += 1
                    logger.debug(
                        "✅ [Apoptosis] Skill %s mantida | health=%.2f",
                        skill.skill.name,
                        health.health_score,
                    )

            # Remove skills marcadas
            for skill in skills_to_remove:
                homocysteine_pool.remove(skill.skill.name)

        except Exception as e:
            logger.error("[Apoptosis] Erro ao avaliar HomocysteinePool: %s", e)

        # 2. Avalia memórias no SearchMemory (Obsidian)
        try:
            from iaglobal.search.search_memory import SearchMemory

            search_memory = SearchMemory()

            pruned_obsidian = await self._prune_obsidian_memories(search_memory)
            result["pruned"] += pruned_obsidian

        except Exception as e:
            logger.error("[Apoptosis] Erro ao avaliar SearchMemory: %s", e)

        # 3. Calcula melhoria de saúde estimada
        if result["evaluated"] > 0:
            result["health_improvement"] = (
                result["pruned"] / result["evaluated"]
            ) * 100  # % de redução de ruído

        logger.info(
            "✅ [Apoptosis] Avaliação completa | evaluated=%d | pruned=%d | saved=%d | improvement=%.1f%%",
            result["evaluated"],
            result["pruned"],
            result["saved"],
            result["health_improvement"],
        )

        return result

    async def _calculate_metabolic_health(self, skill) -> MetabolicHealth:
        """
        Calcula saúde metabólica de uma skill.

        Métricas:
        - age_days: tempo desde criação
        - reuse_count: quantas vezes foi usada
        - success_rate: taxa de sucesso (BanditPolicy)
        - idle_cycles: ciclos sem uso
        - critic_score: qualidade do código (CriticAgent) ← NOVO!
        """
        now = time.time()
        created_at = getattr(skill, "created_at", now)
        age_days = (now - created_at) / 86400  # segundos → dias

        # Reuso count (do metadata)
        metadata = getattr(skill, "metadata", {})
        reuse_count = metadata.get("reuse_count", 0)

        # Success rate (do BanditPolicy)
        try:
            from iaglobal.graphs.bandit import BanditPolicy

            bandit = BanditPolicy()
            metrics = await bandit.get_model_metrics(skill.skill.name)
            success_rate = metrics.get("success_rate", 0.5) if metrics else 0.5
        except:
            success_rate = 0.5

        # Idle cycles (quantos ciclos sem uso)
        last_used = metadata.get("last_used", created_at)
        idle_cycles = max(
            0, int((now - last_used) / 3600)
        )  # horas → ciclos aproximados

        # Bandit IVM (se disponível)
        try:
            bandit_ivm = metadata.get("avg_ivm", 0.5)
        except:
            bandit_ivm = 0.5

        # 🧠 CRITIC SCORE: Avalia qualidade do código gerado
        critic_score = await self._evaluate_with_critic(skill)

        # Calcula health score (0..1)
        health_score = self._calculate_health_score(
            age_days=age_days,
            reuse_count=reuse_count,
            success_rate=success_rate,
            idle_cycles=idle_cycles,
            bandit_ivm=bandit_ivm,
            critic_score=critic_score,
        )

        # Decide apoptose
        should_apoptose, reason, is_pathogenic, is_zombie = self._should_apoptose(
            health_score=health_score,
            age_days=age_days,
            reuse_count=reuse_count,
            success_rate=success_rate,
            idle_cycles=idle_cycles,
            critic_score=critic_score,
        )

        return MetabolicHealth(
            skill_id=skill.skill.name,
            age_days=age_days,
            reuse_count=reuse_count,
            success_rate=success_rate,
            idle_cycles=idle_cycles,
            bandit_ivm=bandit_ivm,
            critic_score=critic_score,
            health_score=health_score,
            should_apoptose=should_apoptose,
            apoptosis_reason=reason,
            is_pathogenic=is_pathogenic,
            is_zombie=is_zombie,
        )

    async def _evaluate_with_critic(self, skill) -> float:
        """
        Usa CriticAgent para avaliar qualidade do código da skill.

        Se skill já tem critic_score no metadata, usa esse valor (evita chamada desnecessária).

        Returns:
            float: 0.0 (péssimo) a 1.0 (excelente)
        """
        # Primeiro, tenta usar critic_score do metadata (já avaliado)
        metadata = getattr(skill, "metadata", {})
        if "critic_score" in metadata:
            return metadata["critic_score"]

        # Se não tem, avalia com CriticAgent
        try:
            from iaglobal.agents.critic_agent import _get_critic

            critic = _get_critic()

            # Extrai código da skill
            code = getattr(skill, "code", "")
            if not code:
                return 0.5  # Neutro se sem código

            # Critic avalia o código
            evaluation = await critic.arbitrar_geracao(
                node_id="critic",
                prompt=f"""
Avalie este código gerado por uma skill evolutiva:

{code[:2000]}  # Primeiros 2000 chars

Critérios:
1. Segurança (não há vulnerabilidades?)
2. Boas práticas (segue padrões?)
3. Funcionalidade (o código funciona?)
4. Manutenibilidade (é legível?)

Nota: 0.0 (péssimo) a 1.0 (excelente)
Retorne APENAS um número.
""",
                task_type="code_evaluation",
            )

            # Extrai nota numérica da resposta
            import re

            numbers = re.findall(r"\d\.?\d*", evaluation)
            if numbers:
                score = float(numbers[0])
                return max(0.0, min(1.0, score))  # Clamp 0..1

            return 0.5  # Default se não conseguir extrair

        except Exception as e:
            logger.debug("[Apoptosis] Critic evaluation failed: %s", e)
            return 0.5  # Neutro em caso de erro

    def _calculate_health_score(
        self,
        age_days: float,
        reuse_count: int,
        success_rate: float,
        idle_cycles: int,
        bandit_ivm: float,
        critic_score: float,  # NOVO!
    ) -> float:
        """
        Calcula score de saúde (0..1) baseado em múltiplas métricas.

        Fórmula:
          health = (age * 0.2) + (reuse * 0.3) + (success * 0.2) + (critic * 0.3)

        O Critic tem peso 30% — qualidade importa mais que quantidade!
        """
        # Age score: skills novas têm score maior (potencial não testado)
        if age_days < 1:
            age_score = 1.0  # Muito nova
        elif age_days < self.criteria.max_age_days:
            age_score = 1.0 - (age_days / self.criteria.max_age_days)
        else:
            age_score = 0.0  # Muito antiga

        # Reuse score: skills muito usadas têm score alto
        if reuse_count >= self.criteria.min_reuse_count * 3:
            reuse_score = 1.0
        elif reuse_count >= self.criteria.min_reuse_count:
            reuse_score = (
                0.5 + (reuse_count / (self.criteria.min_reuse_count * 3)) * 0.5
            )
        else:
            reuse_score = reuse_count / self.criteria.min_reuse_count * 0.5

        # Success score: baseado em success_rate + IVM
        success_score = (success_rate * 0.7) + (bandit_ivm * 0.3)

        # 🧠 Critic score: qualidade do código (peso 30%)
        critic_score_normalized = critic_score  # Já está em 0..1

        # Health score final
        health_score = (
            age_score * self.criteria.weight_age
            + reuse_score * self.criteria.weight_reuse
            + success_score * self.criteria.weight_success
            + critic_score_normalized * self.criteria.weight_critic
        )

        return max(0.0, min(1.0, health_score))

    def _should_apoptose(
        self,
        health_score: float,
        age_days: float,
        reuse_count: int,
        success_rate: float,
        idle_cycles: int,
        critic_score: float,  # NOVO!
    ) -> tuple[bool, str, bool, bool]:
        """
        Decide se skill deve sofrer apoptose.

        Retorna:
            (should_apoptose, reason, is_pathogenic, is_zombie)

        Critérios:
        1. Patogênica: Critic score muito baixo (< 0.4) → código perigoso
        2. Zumbi: Sem uso por muito tempo → código inútil
        3. Health score crítico: Combinação de fatores ruins
        """
        reasons = []
        is_pathogenic = False
        is_zombie = False

        # 🦠 Critério 1: PATOGÊNICA (Critic score baixo = código perigoso)
        if critic_score < self.criteria.min_critic_score:
            is_pathogenic = True
            reasons.append(
                f"pathogenic (critic={critic_score:.2f} < {self.criteria.min_critic_score})"
            )

        # 🧟 Critério 2: ZUMBI (Sem uso + antiga)
        if (
            age_days > self.criteria.max_age_days
            and reuse_count < self.criteria.min_reuse_count
        ):
            is_zombie = True
            reasons.append(f"zombie (age={age_days:.1f}d, reuses={reuse_count})")

        # Critério 3: Health score muito baixo
        if health_score < 0.3:
            reasons.append(f"health_critical ({health_score:.2f})")

        # Critério 4: Success rate muito baixo
        if success_rate < self.criteria.min_success_rate:
            reasons.append(f"low_success_rate ({success_rate:.2f})")

        # Critério 5: Muitos ciclos ociosa
        if idle_cycles > self.criteria.max_idle_cycles:
            reasons.append(f"idle_too_long ({idle_cycles} cycles)")

        if reasons:
            return True, "; ".join(reasons), is_pathogenic, is_zombie

        return False, "", False, False

    async def _prune_obsidian_memories(self, search_memory) -> int:
        """
        Remove memórias antigas do Obsidian (SearchMemory).

        Critério: memórias > 30 dias sem acesso.
        """
        pruned_count = 0

        # Lista todas as memórias
        try:
            from pathlib import Path
            from iaglobal._paths import PACKAGE_DIR

            obsidian_dir = PACKAGE_DIR / "obsidian" / "04_Synapses" / "search_memory"
            if not obsidian_dir.exists():
                return 0

            for md_file in obsidian_dir.glob("*.md"):
                # Verifica idade do arquivo
                mtime = md_file.stat().st_mtime
                age_days = (time.time() - mtime) / 86400

                if age_days > 30:  # 30 dias sem acesso
                    md_file.unlink()
                    pruned_count += 1
                    logger.debug(
                        "[Apoptosis] Memória Obsidian removida: %s (%.1f days)",
                        md_file.name,
                        age_days,
                    )

        except Exception as e:
            logger.error("[Apoptosis] Erro ao podar Obsidian: %s", e)

        return pruned_count

    def get_apoptosis_log(self) -> List[Dict]:
        """Retorna log de apoptoses realizadas."""
        return self.apoptosis_log


# Singleton global
memory_apoptosis = MemoryApoptosis()
