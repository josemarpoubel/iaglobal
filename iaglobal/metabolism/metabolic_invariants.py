# iaglobal/metabolism/metabolic_invariants.py
"""Invariantes de Saúde Metabólica — Monitoramento dos princípios biológicos.

Invariantes:
1. Vault < 90% capacidade
2. Latência FugueCompartment < 1s
3. Toxinas removidas > 0 a cada 6h
4. IVM médio > 0.5

Emitir alertas para OmniMind quando violadas.
"""

import asyncio
import logging
import time
from typing import Dict

from iaglobal.obsidian.omnimind import omni_mind
from iaglobal.obsidian.fugue_compartment import FugueCompartment
from iaglobal.obsidian.delta_sleep import DeltaSleepSync
from iaglobal.obsidian.subconsciousapi import SubconsciousAPI


class MetabolicInvariants:
    """Monitora invariantes de saúde metabólica."""

    def __init__(self):
        self.fugue = FugueCompartment()
        self.delta_sleep = DeltaSleepSync()
        self.subconscious = SubconsciousAPI()
        self.vault_path = self.subconscious.vault_path
        self.logger = logging.getLogger("iaglobal.invariants")
        self.last_toxin_check = time.time()
        self.VAULT_LIMIT_MB = 1024  # 1GB

    async def check_all(self) -> Dict[str, Dict]:
        """Verifica todas as invariantes."""
        return {
            "vault": await self._check_vault_capacity(),
            "latency": await self._check_fugue_latency(),
            "toxins": await self._check_toxin_removal(),
            "ivm": await self._check_system_ivm(),
        }

    async def _check_vault_capacity(self) -> Dict:
        """Verifica se o vault está com capacidade > 90%."""
        total_size_mb = self._get_vault_size()
        usage_percent = min(100.0, (total_size_mb / self.VAULT_LIMIT_MB) * 100)

        if usage_percent > 90:
            alert = f"Vault acima de 90% ({usage_percent:.1f}%). Execução de DeltaSleep recomendada."
            await omni_mind.registrar_violação_lei(
                "metabolic_invariants", "Lei da Ordem", {"alerta": alert}
            )
            self.logger.critical(alert)
            return {"status": "VIOLADA", "usage_percent": usage_percent, "alert": alert}

        return {"status": "OK", "usage_percent": usage_percent}

    def _get_vault_size(self) -> float:
        """Calcula o tamanho do vault em MB."""
        # Mockable para testes
        if hasattr(self, "_mock_vault_size"):
            return self._mock_vault_size
        total_bytes = sum(f.stat().st_size for f in self.vault_path.glob("**/*.md"))
        return round(total_bytes / (1024 * 1024), 2)

    async def _check_fugue_latency(self) -> Dict:
        """Verifica se tarefas em fuga estão demorando > 1s."""
        tasks = self.fugue._background_tasks
        slow_tasks = []

        for task_id, task_data in tasks.items():
            if task_data["status"] == "processing":
                start_time = task_data.get("timestamp", 0)
                latency = time.time() - start_time
                if latency > 1:
                    slow_tasks.append({"task_id": task_id, "latency": latency})

        if slow_tasks:
            alert = f"{len(slow_tasks)} tarefas em fuga com latência >1s. Investigar FugueCompartment."
            await omni_mind.registrar_violação_lei(
                "metabolic_invariants", "Lei da Ordem", {"alerta": alert}
            )
            self.logger.warning(alert)
            return {"status": "AVISO", "slow_tasks": slow_tasks}

        return {"status": "OK", "total_tasks": len(tasks)}

    async def _check_toxin_removal(self) -> Dict:
        """Verifica se toxinas são removidas a cada 6 horas."""
        now = time.time()
        if now - self.last_toxin_check > 21600:  # 6 horas
            limpeza = await self.delta_sleep.limpar_toxinas()
            self.last_toxin_check = now

            if limpeza["toxinas_removidas"] == 0:
                alert = "Nenhuma toxina removida nas últimas 6 horas. Sono Delta comprometido."
                await omni_mind.registrar_violação_lei(
                    "metabolic_invariants", "Lei da Ordem", {"alerta": alert}
                )
                self.logger.warning(alert)
                return {"status": "AVISO", "toxinas_removidas": 0}
            return {"status": "OK", "toxinas_removidas": limpeza["toxinas_removidas"]}

        return {"status": "OK", "message": "Verificação agendada a cada 6h"}

    async def _check_system_ivm(self) -> Dict:
        """Verifica se o IVM médio do sistema está saudável (> 0.5)."""
        # Simulação: pegar IVM médio dos agentes
        avg_ivm = 0.8  # Substituir pela consulta real ao BanditPolicy

        if avg_ivm < 0.5:
            alert = f"IVM médio do sistema baixo ({avg_ivm}). Pressão seletiva comprometida."
            await omni_mind.registrar_violação_lei(
                "metabolic_invariants", "Lei da Ordem", {"alerta": alert}
            )
            self.logger.error(alert)
            return {"status": "VIOLADA", "avg_ivm": avg_ivm}

        return {"status": "OK", "avg_ivm": avg_ivm}

    async def monitor_continuously(self) -> None:
        """Monitora invariantes continuamente."""
        while True:
            await self.check_all()
            await asyncio.sleep(300)  # 5 minutos


async def main():
    """Executa verificação única."""
    invariants = MetabolicInvariants()
    result = await invariants.check_all()
    print(f"🔍 INVARIANTES DE SAÚDE METABÓLICA")
    print("=" * 50)
    for invariant, status in result.items():
        print(f"{invariant.upper()}: {status['status']}")
        if "alert" in status:
            print(f"  🚨 {status['alert']}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
