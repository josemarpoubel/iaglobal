# iaglobal/dashboard/metabolic_sleep_dashboard.py
"""Dashboard de Sono Metabólico — Monitoramento do ciclo REM→Delta→REM.

Objetivo:
- Apresentar métricas do FugueCompartment, DeltaSleepSync e SubconsciousAPI.
- Mostrar status de tarefas em fuga, toxinas removidas e compactações.
- Gerar alertas para invariantes violadas (ex: vault > 90% ocupado).

Métricas Monitoradas:
- Tarefas em processamento: count/status
- Toxinas removidas: count/idade média
- Compactações realizadas: agentes/eficiência
- Capacidade do vault: espaço ocupado
- Eficiência do ciclo REM→Delta: tarefas/hora
"""

import asyncio
import time
from typing import Dict
from pathlib import Path
import logging

from iaglobal.obsidian.fugue_compartment import FugueCompartment
from iaglobal.obsidian.delta_sleep import DeltaSleepSync
from iaglobal.obsidian.subconsciousapi import SubconsciousAPI


class MetabolicSleepDashboard:
    """Dashboard para monitoramento do ciclo de sono metabólico."""

    def __init__(self):
        self.fugue = FugueCompartment()
        self.delta_sleep = DeltaSleepSync()
        self.subconscious = SubconsciousAPI()
        self.logger = logging.getLogger("iaglobal.dashboard")
        self.refresh_interval = 10  # segundos
        self.running = False

    async def coletar_metricas(self) -> Dict[str, Dict]:
        """Coleta métricas dos módulos de sono."""
        # Métricas do FugueCompartment
        tarefas_ativas = len(self.fugue._background_tasks)
        tarefas_processing = len(
            [
                t
                for t in self.fugue._background_tasks.values()
                if t["status"] == "processing"
            ]
        )

        # Métricas do DeltaSleepSync
        limpeza = await self.delta_sleep.limpar_toxinas()
        compactacao = await self.delta_sleep.compactar_memoria("global")

        # Métricas do Vault
        vault_path = self.subconscious.vault_path
        total_tasks = len(list(vault_path.glob("*.md")))
        vault_size = self._get_vault_size(vault_path)

        return {
            "fugue": {
                "total_tasks": tarefas_ativas,
                "processing": tarefas_processing,
                "completed": tarefas_ativas - tarefas_processing,
            },
            "delta": {
                "toxinas_removidas": limpeza["toxinas_removidas"],
                "compactacoes": compactacao["total_tarefas"],
                "tipos_consolidados": len(compactacao["tipos_consolidados"]),
            },
            "vault": {
                "total_notas": total_tasks,
                "tamanho_mb": vault_size,
                "capacidade_used": self._get_vault_usage_percent(vault_path),
            },
            "eficiencia": {
                "tarefas_por_hora": self._calcular_eficiciencia(),
                "ultima_sincronia": int(time.time()),
            },
        }

    def _get_vault_size(self, vault_path: Path) -> float:
        """Calcula o tamanho total do vault em MB."""
        total_bytes = sum(f.stat().st_size for f in vault_path.glob("**/*.md"))
        return round(total_bytes / (1024 * 1024), 2)

    def _get_vault_usage_percent(self, vault_path: Path) -> float:
        """Calcula percentual de uso do vault (simplificado)."""
        # Em um ambiente real, comparar com limite físico do disco
        return min(100.0, self._get_vault_size(vault_path) / 1024 * 100)  # 1GB limite

    def _calcular_eficiciencia(self) -> float:
        """Calcula tarefas processadas por hora (simplificado)."""
        # Em produção, usar histórico de métricas
        return round(self.fugue._background_tasks.__len__() / 24, 2)  # Mock

    async def exibir_dashboard(self) -> None:
        """Exibe o dashboard no terminal."""
        while self.running:
            metricas = await self.coletar_metricas()

            # Limpar tela (ANSI)
            print("\033[H\033[J", end="")

            # Cabeçalho
            print("🌙 ⚡ DASHBOARD DE SONO METABÓLICO ⚡ 🌙")
            print(
                f"Última atualização: {time.ctime(metricas['eficiencia']['ultima_sincronia'])}"
            )
            print("=" * 60)

            # Seção FugueCompartment
            print("\n🔮 COMPARTIMENTO DE FUGA")
            print(
                f"  Tarefas ativas: {metricas['fugue']['total_tasks']} ",
                f"(⏳ Processing: {metricas['fugue']['processing']}, ✅ Completed: {metricas['fugue']['completed']})",
            )

            # Seção DeltaSleepSync
            print("\n🌌 SONO DELTA (Consolidação)")
            print(f"  Toxinas removidas: {metricas['delta']['toxinas_removidas']}")
            print(
                f"  Compactações: {metricas['delta']['compactacoes']} ",
                f"(Tipos: {metricas['delta']['tipos_consolidados']})",
            )

            # Seção Vault
            print("\n💾 VAULT SUBCONSCIENTE")
            print(f"  Notas armazenadas: {metricas['vault']['total_notas']}")
            print(
                f"  Tamanho: {metricas['vault']['tamanho_mb']} MB ",
                f"(🟢 {metricas['vault']['capacidade_used']:.1f}% usado)",
            )

            # Seção Eficiência
            print("\n⚡ EFICIÊNCIA METABÓLICA")
            print(f"  Tarefas/hora: {metricas['eficiencia']['tarefas_por_hora']}")

            # Alertas
            print("\n🚨 ALERTAS")
            if metricas["vault"]["capacidade_used"] > 90:
                print("  ❗ VAULT CHEIO: Execução de sono delta recomendada!")
            else:
                print("  Nenhum alerta ativo.")

            # Rodapé
            print("\n" + "=" * 60)
            print("🔄 Pressione Ctrl+C para sair")

            await asyncio.sleep(self.refresh_interval)

    async def iniciar(self) -> None:
        """Inicia o dashboard."""
        self.running = True
        try:
            await self.exibir_dashboard()
        except asyncio.CancelledError:
            self.logger.info("Dashboard de sono interrompido.")
        finally:
            self.running = False

    async def parar(self) -> None:
        """Para o dashboard."""
        self.running = False


async def main():
    """Entry point para execução standalone do dashboard."""
    dashboard = MetabolicSleepDashboard()
    await dashboard.iniciar()


if __name__ == "__main__":
    asyncio.run(main())
