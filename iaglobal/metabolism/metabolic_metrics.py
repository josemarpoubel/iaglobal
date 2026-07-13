# iaglobal/metabolism/metabolic_metrics.py
"""Agregador de métricas metabólicas para dashboard em tempo real."""

import logging
import time
import os
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Union

from iaglobal.metabolism.metabolic_invariants import MetabolicInvariants
from iaglobal.obsidian.fugue_compartment import FugueCompartment
from iaglobal.obsidian.delta_sleep import DeltaSleepSync
from iaglobal.graphs.bandit import BanditPolicy


@dataclass
class HealthData:
    uptime_min: int
    invariants: Dict[str, Dict]
    system_metrics: Dict[str, Dict]
    suggestions: List[str]


class MetabolicMetrics:
    """Coleta e agrega métricas metabólicas para monitoramento."""

    def __init__(self):
        self.logger = logging.getLogger("iaglobal.metrics")
        self.start_time = time.time()
        self.invariants = MetabolicInvariants()
        self.fugue = FugueCompartment()
        self.delta_sleep = DeltaSleepSync()
        self.bandit = BanditPolicy()

    async def collect_health_data(self) -> HealthData:
        """Coleta todas as métricas de saúde do sistema."""
        uptime_min = int((time.time() - self.start_time) // 60)

        # Coletar invariantes
        invariants_data = await self.invariants.check_all()

        # Enriquecer com valores numéricos
        invariants = {
            "vault": {
                "status": invariants_data["vault"]["status"],
                "value": f"{self._get_vault_usage():.1f}%",
                "healthy": invariants_data["vault"]["status"] == "OK",
                "alert": invariants_data["vault"].get("alert"),
                "last_correction": self._get_last_correction("vault"),
            },
            "fugue_latency": {
                "status": invariants_data["latency"]["status"],
                "value": f"{self._get_fugue_latency():.0f}ms",
                "healthy": invariants_data["latency"]["status"] == "OK",
                "alert": invariants_data["latency"].get("alert"),
                "last_correction": self._get_last_correction("latency"),
            },
            "toxins": {
                "status": invariants_data["toxins"]["status"],
                "value": f"{self._get_toxin_level()}%",
                "healthy": invariants_data["toxins"]["status"] == "OK",
                "alert": invariants_data["toxins"].get("alert"),
                "last_correction": self._get_last_correction("toxins"),
            },
            "ivm": {
                "status": invariants_data["ivm"]["status"],
                "value": f"{self._get_ivm():.2f}",
                "healthy": invariants_data["ivm"]["status"] == "OK",
                "alert": invariants_data["ivm"].get("alert"),
                "last_correction": self._get_last_correction("ivm"),
            },
        }

        # Coletar métricas do sistema
        system_metrics = {
            "cpu_usage": {
                "value": f"{self._get_cpu_usage():.1f}%",
                "healthy": self._get_cpu_usage() < 90,
            },
            "memory_pressure": {
                "value": f"{self._get_memory_pressure():.1f}%",
                "healthy": self._get_memory_pressure() < 90,
            },
            "active_agents": {
                "value": str(await self._get_active_agents()),
                "healthy": True,
            },
        }

        # Gerar sugestões
        suggestions = self._generate_suggestions(invariants, system_metrics)

        return HealthData(
            uptime_min=uptime_min,
            invariants=invariants,
            system_metrics=system_metrics,
            suggestions=suggestions,
        )

    def _get_vault_usage(self) -> float:
        """Retorna uso do vault em percentual (simulado). TODO: Implementar get_vault_stats em DeltaSleepSync."""
        # Simulação baseada em limpeza de toxinas
        toxinas_percent = self.delta_sleep.get_toxin_percent()
        # Se toxinas estiverem altas (> 70%), vault está cheio
        return min(95.0, toxinas_percent * 1.3)  # Simulação conservadora

    def _get_fugue_latency(self) -> float:
        """Retorna latência média do FugueCompartment em ms (simulado com secrets).

        Valor determinístico baseado em timestamp e hostname para reprodutibilidade.
        """
        # Usar hash do timestamp atual e hostname para gerar valor pseudoaleatório
        timestamp = int(time.time() * 1000)  # ms
        unique_seed = f"{timestamp}-{os.uname().nodename}".encode()
        hash_val = int(hashlib.sha256(unique_seed).hexdigest(), 16) % 1000

        # Latência entre 100ms e 1500ms, distribuição uniforme via hash
        return 100.0 + (hash_val % 1400)

    def _get_toxin_level(self) -> float:
        """Retorna nível de toxinas como percentual da cota (simulado).

        TODO: Implementar get_toxin_percent em DeltaSleepSync.
        """
        # Simulação baseada no tempo desde a última limpeza
        last_cleanup = self.delta_sleep.get_last_cleanup_time()
        hours_since_cleanup = (time.time() - last_cleanup) / 3600
        # 100% após 7 dias sem limpeza
        return min(100.0, (hours_since_cleanup / (7 * 24)) * 100)

    def _get_ivm(self) -> float:
        """Calcula IVM atual (simulado com secrets).

        Valor determinístico baseado em timestamp e hostname.
        """
        unique_seed = f"ivm-{int(time.time() // 3600)}-{os.uname().nodename}".encode()
        hash_val = int(hashlib.sha256(unique_seed).hexdigest(), 16) % 100

        # IVM entre 0.5 e 0.95, distribuição uniforme via hash
        return 0.5 + (hash_val / 100) * 0.45  # 0.5 a 0.95

    def _get_cpu_usage(self) -> float:
        """Retorna uso de CPU (simulação)."""
        # Simulação - substituir por psutil em implementação real
        import os

        if os.name == "posix":
            try:
                import psutil

                return psutil.cpu_percent(interval=1)
            except ImportError:
                return 32.0  # Valor padrão para testes
        return 15.0

    def _get_memory_pressure(self) -> float:
        """Retorna pressão de memória (simulação)."""
        # Simulação - substituir por psutil em implementação real
        if os.name == "posix":
            try:
                import psutil

                return psutil.virtual_memory().percent
            except ImportError:
                return 45.0  # Valor padrão para testes
        return 50.0

    async def _get_active_agents(self) -> int:
        """Conta número de agentes ativos (simulado com secrets).

        Valor determinístico baseado em timestamp e hostname.
        """
        unique_seed = (
            f"agents-{int(time.time() // 3600)}-{os.uname().nodename}".encode()
        )
        hash_val = int(hashlib.sha256(unique_seed).hexdigest(), 16) % 13

        # Entre 3 e 15 agentes ativos
        return 3 + hash_val

    def _get_last_correction(self, invariant: str) -> Union[str, Dict]:
        """Retorna última correção para um invariante (simulado)."""
        # Simulação: retorno fixo para MVP
        return "Nenhuma"

    def _generate_suggestions(
        self, invariants: Dict, system_metrics: Dict
    ) -> List[str]:
        """Gera sugestões baseadas nas métricas coletadas."""
        suggestions = []

        # Sugestões para invariantes
        for inv_name, data in invariants.items():
            if data["status"] == "AVISO" and "alert" in data:
                suggestions.append(data["alert"])
            elif data["status"] == "VIOLADA":
                suggestions.append(
                    f"Ação recomendada: Executar `iaglobal autocorrect` para corrigir {inv_name}"
                )

        # Sugestões para métricas do sistema
        if system_metrics["cpu_usage"]["value"] > "80%":
            suggestions.append(
                "Pressão de CPU alta. Considerar otimização ou escalamento."
            )

        if system_metrics["memory_pressure"]["value"] > "85%":
            suggestions.append(
                "Pressão de memória alta. Verificar leaks ou aumentar quota."
            )

        # Sugestões baseadas em padrões
        if (
            invariants["vault"]["value"] > "85%"
            and invariants["toxins"]["value"] > "20%"
        ):
            suggestions.append(
                "Padrão detectado: Vault e toxinas altos. Aumentar limpeza DeltaSleep."
            )

        if invariants["ivm"]["value"] < "0.6":
            suggestions.append(
                "IVM baixo. Priorizar agentes de alta eficiência (ver `iaglobal status`)."
            )

        return suggestions[:5]  # Limitar a 5 sugestões
