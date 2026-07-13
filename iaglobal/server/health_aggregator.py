# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Health Aggregator — Coleta e consolida saúde de todos os serviços iaglobal.

Responsável por:
- Consultar saúde de MCP, UI, Evolution em paralelo
- Agregar em formato padronizado (FHIR-like)
- Calcular status geral do organismo (healthy/degraded/unhealthy)
- Expor métricas metabólicas (IVM, CPU budget, agentes ativos)

AXIOMAS IMPLEMENTADOS:
- AXIOMA 1 (Homeostase): Sensor de estado endógeno do organismo
- AXIOMA 8 (Sinalização): Broadcast de saúde via HTTP
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from pathlib import Path

import httpx

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.server.health")


@dataclass
class ServiceHealth:
    """Saúde de um serviço individual."""

    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    uptime: float = 0.0
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class HealthAggregator:
    """Coleta saúde de todos os serviços via HTTP."""

    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = vault_path
        self.services = {
            "gateway": "http://localhost:8000/health",
            "mcp": "http://localhost:8100/health",
            "ui": "http://localhost:8765/health",
            "evolution": "http://localhost:8002/evolution/health",
        }
        self.timeout = httpx.Timeout(2.0)  # 2s por serviço

    async def check_all(self) -> Dict[str, ServiceHealth]:
        """
        Consulta todos os serviços em paralelo.

        Returns:
            Dict com nome do serviço → ServiceHealth
        """
        start_time = time.time()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = {
                name: self._check_service(client, name, url)
                for name, url in self.services.items()
            }
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        elapsed = (time.time() - start_time) * 1000
        logger.info(
            "[HEALTH] Check completo em %.0fms | serviços=%d", elapsed, len(results)
        )

        health_map = {
            name: result
            if isinstance(result, ServiceHealth)
            else self._error_to_health(name, result)
            for name, result in zip(tasks.keys(), results)
        }

        return health_map

    async def _check_service(
        self, client: httpx.AsyncClient, name: str, url: str
    ) -> ServiceHealth:
        """Consulta saúde de um serviço específico."""
        try:
            start = time.time()
            response = await client.get(url)
            latency = (time.time() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                return ServiceHealth(
                    name=name,
                    status=data.get("status", "healthy"),
                    uptime=data.get("uptime", 0),
                    latency_ms=latency,
                    details=data,
                )
            else:
                logger.warning(
                    "[HEALTH] Serviço %s retornou status %d", name, response.status_code
                )
                return ServiceHealth(
                    name=name,
                    status="degraded",
                    latency_ms=latency,
                    details={"status_code": response.status_code},
                )

        except httpx.TimeoutException as e:
            logger.warning("[HEALTH] Timeout no serviço %s: %s", name, e)
            return ServiceHealth(
                name=name, status="unhealthy", error=f"timeout: {str(e)}"
            )

        except httpx.ConnectError as e:
            logger.warning("[HEALTH] Erro de conexão no serviço %s: %s", name, e)
            return ServiceHealth(
                name=name, status="unhealthy", error=f"connection: {str(e)}"
            )

        except Exception as e:
            logger.exception("[HEALTH] Erro inesperado no serviço %s: %s", name, e)
            return ServiceHealth(
                name=name, status="unhealthy", error=f"unexpected: {str(e)}"
            )

    @staticmethod
    def _error_to_health(name: str, error: Exception) -> ServiceHealth:
        """Converte exceção em ServiceHealth."""
        return ServiceHealth(name=name, status="unhealthy", error=str(error))

    @staticmethod
    def compute_overall_status(health_map: Dict[str, ServiceHealth]) -> str:
        """
        Calcula status geral do organismo baseado na saúde dos serviços.

        Regras:
        - Todos healthy → "healthy"
        - Algum degraded, nenhum unhealthy → "degraded"
        - Algum unhealthy → "unhealthy"
        - Gateway unhealthy → "unhealthy" (crítico)
        """
        statuses = [h.status for h in health_map.values()]

        # Gateway é crítico
        if (
            health_map.get("gateway", ServiceHealth("gateway", "unknown")).status
            == "unhealthy"
        ):
            return "unhealthy"

        # Pelo menos um unhealthy
        if "unhealthy" in statuses:
            return "unhealthy"

        # Pelo menos um degraded
        if "degraded" in statuses:
            return "degraded"

        return "healthy"

    async def get_metabolic_state(self) -> Dict[str, Any]:
        """
        Coleta estado metabólico do sistema (IVM, CPU, agentes).

        Returns:
            Dict com métricas metabólicas
        """
        try:
            from iaglobal.chappie import _get_chappie

            chappie = _get_chappie()
            ivm = chappie.get("ivm") if chappie else None

            if ivm:
                ranking = ivm.get_ranking()
                agents_ativos = len(ranking)
                ivm_medio = (
                    sum(r["current_ivm"] for r in ranking) / agents_ativos
                    if agents_ativos
                    else 0
                )
                peak_ivm = max((r["current_ivm"] for r in ranking), default=0)

                return {
                    "ivm_medio": round(ivm_medio, 3),
                    "peak_ivm": round(peak_ivm, 3),
                    "agents_ativos": agents_ativos,
                    "agents_excelentes": sum(
                        1 for r in ranking if r["current_ivm"] >= 0.8
                    ),
                    "agents_criticos": sum(
                        1 for r in ranking if r["current_ivm"] < 0.3
                    ),
                }
            else:
                return {
                    "ivm_medio": 0,
                    "peak_ivm": 0,
                    "agents_ativos": 0,
                    "status": "ivm_unavailable",
                }

        except Exception as e:
            logger.debug("[HEALTH] Falha ao coletar estado metabólico: %s", e)
            return {
                "ivm_medio": 0,
                "peak_ivm": 0,
                "agents_ativos": 0,
                "status": "error",
                "error": str(e),
            }

    async def get_cpu_state(self) -> Dict[str, Any]:
        """
        Coleta estado de CPU (budgets, alocação).

        Returns:
            Dict com métricas de CPU
        """
        try:
            from iaglobal.execution.cpu_affinity import cpu_affinity

            budgets = await cpu_affinity.get_all_budgets()
            metrics = await cpu_affinity.get_all_metrics()

            total_budget = sum(budgets.values())
            agents_em_sobrevivencia = sum(
                1 for m in metrics.values() if m.get("em_modo_sobrevivencia", False)
            )

            return {
                "total_budget_alocado": round(total_budget, 3),
                "agents_com_budget": len(budgets),
                "agents_em_sobrevivencia": agents_em_sobrevivencia,
                "budget_medio": round(total_budget / len(budgets), 3) if budgets else 0,
            }

        except Exception as e:
            logger.debug("[HEALTH] Falha ao coletar estado de CPU: %s", e)
            return {
                "total_budget_alocado": 0,
                "agents_com_budget": 0,
                "status": "error",
                "error": str(e),
            }

    async def get_immune_state(self) -> Dict[str, Any]:
        """
        Coleta estado do sistema imunológico (entropia, barreiras, quarentena).

        Returns:
            Dict com métricas imunológicas
        """
        try:
            from iaglobal.observability.entropy_interceptor import (
                get_immune_state as get_entropy_state,
            )
            from iaglobal.immunity.metabolic_immune_barrier import barrier
            from iaglobal.immunity.immune_orchestrator import immune_orchestrator
            from iaglobal.immunity.glutathione_pool import GlutathionePool
            from iaglobal.core.few_shot_provider import (
                few_shot_provider,
                LRU_CACHE_SIZE,
                MAX_VACCINE_AGE_DAYS,
                ESTIMATED_TOKENS_PER_EXAMPLE,
            )
            from iaglobal.core.mitochondrial_probe import mitochondrial_probe

            # Entropia (EntropySentinel)
            entropy_state = get_entropy_state()

            # Barreira Imunológica (MetabolicImmuneBarrier)
            barrier_counts = barrier.counts()
            barrier_degraded = barrier.is_degraded()

            # Immune Orchestrator (quarentena, detectores ativos)
            immune_health = immune_orchestrator.health_check()

            # Glutathione (guardrails ativos)
            guardrails_count = GlutathionePool().count()

            # FewShot Cache (sinal de saúde cognitiva)
            cache_size = len(few_shot_provider._embedding_cache)
            cache_usage_pct = (
                (cache_size / LRU_CACHE_SIZE * 100) if LRU_CACHE_SIZE > 0 else 0
            )

            # Métricas de vacinas DLQ (Mutação 1C)
            now = time.monotonic()
            oldest_vaccine_age_days = 0
            if few_shot_provider._example_cache:
                oldest_timestamp = min(
                    ts for _, ts in few_shot_provider._example_cache.values()
                )
                oldest_vaccine_age_days = (now - oldest_timestamp) / 86400

            negative_examples_count = len(few_shot_provider._negative_examples)
            estimated_token_overhead = (
                negative_examples_count * ESTIMATED_TOKENS_PER_EXAMPLE
            )

            return {
                "entropia": entropy_state,
                "barreira": {
                    "degraded": barrier_degraded,
                    "events": barrier_counts,
                },
                "quarantine": {
                    "skills": immune_health.get("quarantined_skills", 0),
                    "active_detectors": immune_health.get("active_detectors", 0),
                },
                "glutathione": {
                    "guardrails_ativos": guardrails_count,
                },
                "cognitive": {
                    "embedding_cache_size": cache_size,
                    "embedding_cache_limit": LRU_CACHE_SIZE,
                    "embedding_cache_usage_pct": round(cache_usage_pct, 1),
                    "cache_health": "high"
                    if cache_usage_pct > 80
                    else "normal"
                    if cache_usage_pct > 30
                    else "low",
                    # Métricas de vacinas DLQ (Mutação 1C)
                    "few_shot": {
                        "negative_examples_count": negative_examples_count,
                        "oldest_vaccine_age_days": round(oldest_vaccine_age_days, 1),
                        "estimated_token_overhead": estimated_token_overhead,
                        "max_vaccine_age_days": MAX_VACCINE_AGE_DAYS,
                        "expiry_status": "ok"
                        if oldest_vaccine_age_days < MAX_VACCINE_AGE_DAYS
                        else "expiry_soon",
                    },
                },
                # Estado metabólico (MitochondrialProbe - Integração #3)
                "metabolic_state": {
                    "mitochondrial": mitochondrial_probe.get_health_status(),
                },
            }

        except Exception as e:
            logger.debug("[HEALTH] Falha ao coletar estado imunológico: %s", e)
            return {
                "entropia": {},
                "barreira": {"degraded": False, "events": {}},
                "quarantine": {"skills": 0, "active_detectors": 0},
                "glutathione": {"guardrails_ativos": 0},
                "cognitive": {
                    "embedding_cache_size": 0,
                    "embedding_cache_limit": 0,
                    "embedding_cache_usage_pct": 0,
                    "cache_health": "unknown",
                },
                "status": "error",
                "error": str(e),
            }


# Instância global singleton
health_aggregator = HealthAggregator()
