# iaglobal/metabolism/metabolic_autocorrect.py
"""Autocorreção de Invariantes — Respostas automáticas para violações de saúde metabólica.

Ações Corretivas:
- Vault > 90% → Acionar DeltaSleepSync
- Fugue Latency > 1s → Pausar novas tarefas e acionar compactação
- Toxinas = 0 → Forçar limpeza em 1x por dia
- IVM < 0.5 → Ajustar BanditPolicy

Todas as ações são registradas no OmniMind como "aprendizado emergencial".
"""

import asyncio
import logging
from typing import Dict

from iaglobal.obsidian.omnimind import omni_mind
from iaglobal.metabolism.metabolic_invariants import MetabolicInvariants
from iaglobal.subconscious.delta_sleep import DeltaSleepSync
from iaglobal.graphs.bandit import BanditPolicy


class MetabolicAutocorrect:
    """Aplica correções automáticas para invariantes violadas."""

    def __init__(self):
        self.logger = logging.getLogger("iaglobal.autocorrect")
        self.invariants = MetabolicInvariants()
        self.delta_sleep = DeltaSleepSync()
        self.bandit = BanditPolicy()
        self.AUTOCHECK_INTERVAL = 300  # 5 minutos

    async def verificar_e_corrigir(self) -> Dict[str, Dict]:
        """Verifica invariantes e aplica correções automáticas."""
        resultados = await self.invariants.check_all()
        correcoes = {}
        
        # Vault > 90% → Acionar DeltaSleep
        if resultados["vault"]["status"] == "VIOLADA":
            await self._corrigir_vault_cheio()
            correcoes["vault"] = {"acao": "delta_sleep_acionado", "status": "executado"}
        
        # Fugue Latency > 1s → Pausar e compactar
        if resultados["latency"]["status"] == "AVISO":
            await self._corrigir_fugue_latencia()
            correcoes["latency"] = {"acao": "fugue_compactado", "status": "executado"}
        
        # Toxinas = 0 → Forçar limpeza 1x/dia
        if resultados["toxins"]["status"] == "AVISO":
            await self._corrigir_toxinas_estagnadas()
            correcoes["toxins"] = {"acao": "limpeza_forcada", "status": "executado"}
        
        # IVM < 0.5 → Ajustar BanditPolicy
        if resultados["ivm"]["status"] == "VIOLADA":
            await self._corrigir_ivm_baixo()
            correcoes["ivm"] = {"acao": "bandit_ajustado", "status": "executado"}
        
        if correcoes:
            self.logger.info(f"🛠️ Correções automáticas aplicadas: {correcoes}")
        return {
            "invariantes": resultados,
            "correcoes": correcoes,
        }

    async def _corrigir_vault_cheio(self) -> None:
        """Aciona DeltaSleep para limpeza emergencial."""
        self.logger.warning("Vault acima de 90%. Acionando DeltaSleep emergencial...")
        limpeza = await self.delta_sleep.limpar_toxinas()
        compactacao = self.delta_sleep.compactar_memoria("emergencial")
        
        await omni_mind.registrar_violação_lei(
            agente_id="metabolic_autocorrect",
            lei="Lei da Ordem",
            mensagem=f"DeltaSleep emergencial: toxinas_removidas={limpeza['toxinas_removidas']}, compactacoes={compactacao['total_tarefas']}",
        )

    async def _corrigir_fugue_latencia(self) -> None:
        """Pausa novas tarefas e compacta FugueCompartment."""
        self.logger.warning("Latência alta no FugueCompartment. Compactando tarefas...")
        # Simulação: pausar novas tarefas
        from iaglobal.subconscious.fugue_compartment import FugueCompartment
        fugue = FugueCompartment()
        for task_id, task_data in fugue._background_tasks.items():
            if task_data["status"] == "processing":
                task_data["status"] = "paused"
        
        # Compactar memória
        compactacao = self.delta_sleep.compactar_memoria("fugue")
        
        await omni_mind.registrar_violação_lei(
            agente_id="metabolic_autocorrect",
            lei="Lei da Ordem",
            mensagem=f"Fugue compactado: tarefas_pausadas={len(fugue._background_tasks)}, compactacoes={compactacao['total_tarefas']}",
        )

    async def _corrigir_toxinas_estagnadas(self) -> None:
        """Força limpeza de toxinas 1x por dia."""
        self.logger.warning("Toxinas estagnadas. Forçando limpeza diária...")
        limpeza = await self.delta_sleep.limpar_toxinas()
        
        await omni_mind.registrar_violação_lei(
            agente_id="metabolic_autocorrect",
            lei="Lei da Ordem",
            mensagem=f"Limpeza forçada: toxinas_removidas={limpeza['toxinas_removidas']}",
        )

    async def _corrigir_ivm_baixo(self) -> None:
        """Ajusta BanditPolicy para priorizar agentes de alta performance."""
        self.logger.warning("IVM baixo. Ajustando BanditPolicy...")
        await self.bandit.ajustar_por_ivm()
        
        await omni_mind.registrar_violação_lei(
            agente_id="metabolic_autocorrect",
            lei="Lei da Ordem",
            mensagem="BanditPolicy ajustado para priorizar agentes de alta performance",
        )

    async def monitorar_e_corrigir(self) -> None:
        """Monitora invariantes continuamente e aplica correções."""
        while True:
            await self.verificar_e_corrigir()
            await asyncio.sleep(self.AUTOCHECK_INTERVAL)


async def main():
    """Executa verificação e correção única."""
    autocorrect = MetabolicAutocorrect()
    result = await autocorrect.verificar_e_corrigir()
    print("🛠️ AUTO-CORREÇÃO DE INVARIANTES")
    print("=" * 50)
    for invariant, status in result["invariantes"].items():
        print(f"{invariant.upper()}: {status['status']}")
        if "alert" in status:
            print(f"  🚨 {status['alert']}")
    if result["correcoes"]:
        print("\n🔧 CORREÇÕES APLICADAS:")
        for invariant, correcao in result["correcoes"].items():
            print(f"  {invariant.upper()}: {correcao['acao']}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())