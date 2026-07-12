import asyncio
from datetime import datetime, UTC
from typing import Optional, TYPE_CHECKING
from pathlib import Path

from iaglobal._paths import PACKAGE_DIR
from iaglobal.utils.logger import get_logger
from iaglobal.tools.search import async_search_tool

if TYPE_CHECKING:
    from iaglobal.policy.bandit_evolutivo import BanditPolicyEvolutiva

logger = get_logger("iaglobal.chappie.bandit_evolution")


class BanditPolicyEvolution:
    def __init__(
        self,
        epsilon: float = 0.2,
        decay: float = 0.995,
        min_sample_size: int = 10,
        db_path: Optional[Path] = None,
    ):
        from iaglobal.policy.bandit_evolutivo import BanditPolicyEvolutiva as _Base

        if db_path is None:
            db_path = PACKAGE_DIR / "memory" / "bandit_evolution.json"

        self._base = _Base(
            epsilon=epsilon,
            decay=decay,
            min_sample_size=min_sample_size,
            db_path=db_path,
        )

        self._learning_cycle_running = False
        self._cycles_completed = 0
        self._last_web_learn: Optional[datetime] = None

        logger.info("[BanditEvolution] Chappie BanditEvolution inicializado")

    def __getattr__(self, name):
        return getattr(self._base, name)

    @property
    def fitness_records(self):
        return self._base.fitness_records

    @property
    def banned_providers(self):
        return self._base.banned_providers

    @property
    def min_fitness_for_selection(self):
        return self._base.min_fitness_for_selection

    async def autonomous_cycle(self) -> dict:
        if self._learning_cycle_running:
            return {"status": "already_running"}
        self._learning_cycle_running = True
        try:
            result = await self._executar_ciclo_autonomo()
            self._cycles_completed += 1
            return result
        finally:
            self._learning_cycle_running = False

    async def aprender_com_busca(self, query: str) -> str:
        try:
            logger.info("[BanditEvolution] Buscando: %s", query)
            resultado = await async_search_tool(f"melhores modelos IA {query} 2026")
            if resultado:
                await self._registrar_aprendizado_obsidian(query, resultado)
                logger.info("[BanditEvolution] Aprendizado registrado no Obsidian")
            return resultado
        except Exception as e:
            logger.warning("[BanditEvolution] Falha na busca: %s", e)
            return ""

    async def _executar_ciclo_autonomo(self) -> dict:
        metrics = {
            "providers_analisados": len(self._base.fitness_records),
            "providers_banidos": len(self._base.banned_providers),
            "fitness_medio": 0.0,
            "buscas_realizadas": 0,
            "aprendizados_consolidados": 0,
        }

        if self._base.fitness_records:
            scores = [r.fitness_score for r in self._base.fitness_records.values()]
            metrics["fitness_medio"] = sum(scores) / len(scores) if scores else 0.0

        providers_ruins = [
            pid for pid, rec in self._base.fitness_records.items()
            if rec.fitness_score < self._base.min_fitness_for_selection and rec.total_uses >= 5
        ]

        if providers_ruins:
            await self.aprender_com_busca(" OR ".join(providers_ruins[:3]))
            metrics["buscas_realizadas"] = 1
            metrics["aprendizados_consolidados"] = len(providers_ruins)

        self._last_web_learn = datetime.now(UTC)
        self._base._salvar_estado()

        logger.info(
            "[BanditEvolution] Ciclo autonomo concluido | providers=%d fitness_medio=%.3f buscas=%d",
            metrics["providers_analisados"],
            metrics["fitness_medio"],
            metrics["buscas_realizadas"],
        )
        return metrics

    async def _registrar_aprendizado_obsidian(self, query: str, resultado: str) -> None:
        try:
            from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
            sub = SubconsciousAPI()
            await sub.escrever_curto_prazo(
                nome=f"bandit_learn_{datetime.now(UTC).timestamp():.0f}",
                conteudo=(
                    f"## Aprendizado por Busca - BanditEvolution\n\n"
                    f"- **Query**: {query}\n"
                    f"- **Timestamp**: {datetime.now(UTC).isoformat()}\n\n"
                    f"### Resultado\n\n{resultado[:2000]}\n"
                ),
                tags=["#bandit", "#evolution", "#aprendizado"],
            )
        except Exception as e:
            logger.warning("[BanditEvolution] Falha ao registrar no Obsidian: %s", e)

    def get_status_evolution(self) -> dict:
        try:
            base = self._base.get_status_evolutivo()
        except Exception:
            base = {}
        base.update({
            "ciclos_completados": self._cycles_completed,
            "ultimo_web_learn": self._last_web_learn.isoformat() if self._last_web_learn else None,
            "learning_cycle_running": self._learning_cycle_running,
            "componente": "chappie",
        })
        return base


_bandit_evolution_instance: Optional["BanditPolicyEvolution"] = None


def get_bandit_evolution() -> "BanditPolicyEvolution":
    global _bandit_evolution_instance
    if _bandit_evolution_instance is None:
        _bandit_evolution_instance = BanditPolicyEvolution()
    return _bandit_evolution_instance


def init_bandit_evolution(**kwargs) -> "BanditPolicyEvolution":
    global _bandit_evolution_instance
    _bandit_evolution_instance = BanditPolicyEvolution(**kwargs)
    return _bandit_evolution_instance
