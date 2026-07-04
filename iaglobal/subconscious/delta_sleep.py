# iaglobal/subconscious/delta_sleep.py
"""DeltaSleepSync — Simula o sono delta para limpeza e compactação de vault.

Objetivo:
- Compactar memórias brutas (metadados duplicados, context_effects obsoletos).
- Eliminar "toxinas cognitivas" (dados não referenciados).
- Sincronizar com o FugueCompartment para ciclo REM→Delta→REM.
"""

import asyncio
import time
from typing import Dict, Any, List
from iaglobal.subconscious.subconscious_api import SubconsciousAPI


class DeltaSleepSync:
    """Gerencia a fase de sono delta para limpeza de vault."""

    def __init__(self):
        self.subconscious = SubconsciousAPI()
        self.TOXIN_THRESHOLD_DAYS = 7 # Memórias não acessadas há 7 dias são "tóxicas"
        self._last_cleanup_time = time.time()  # Inicializar timestamp

    def get_vault_stats(self) -> tuple[float, float]:
        """Retorna (total, used) em MB ou GB. Simulação para MVP."""
        # Simulação: vault de 10GB, uso variável
        total = 10.0  # GB
        toxinas_percent = self.get_toxin_percent()
        used = (toxinas_percent / 100) * total  # GB
        return total, used

    def get_toxin_percent(self) -> float:
        """Retorna percentual de toxinas no vault (0-100)."""
        # Simulação baseada no tempo desde a última limpeza
        hours_since_cleanup = (time.time() - self._last_cleanup_time) / 3600
        # 100% após 7 dias sem limpeza
        return min(100.0, (hours_since_cleanup / (7 * 24)) * 100)

    def get_last_cleanup_time(self) -> float:
        """Retorna timestamp da última limpeza."""
        return self._last_cleanup_time

    async def limpar_toxinas(self) -> Dict[str, int]:
        """Remove memórias não acessadas (toxinas) do vault."""
        # Buscar todas as tarefas registradas
        tarefas = self.subconscious.buscar_tarefas(
            origem="fugue_compartment",
            filtro={"status": {"$in": ["completed", "failed"]}},
        )
        
        # Identificar toxinas
        toxinas = []
        for tarefa in tarefas:
            metadados = tarefa.get("metadados", {})
            last_accessed = metadados.get("timestamp", 0)
            if self._eh_toxina(last_accessed):
                toxinas.append(tarefa["task_id"])
        
        # Remover toxinas
        removed_count = 0
        for task_id in toxinas:
            self.subconscious.remover_tarefa(task_id)
            removed_count += 1
        
        return {"toxinas_removidas": removed_count, "total_verificado": len(tarefas)}

    def _eh_toxina(self, last_accessed: float) -> bool:
        """Verifica se uma memória é tóxica (não acessada há muito tempo)."""
        import time
        return (time.time() - last_accessed) > (self.TOXIN_THRESHOLD_DAYS * 86400)

    def compactar_memoria(self, agent_id: str) -> Dict[str, Any]:
        """Compacta memórias de um agente específico."""
        tarefas = self.subconscious.buscar_tarefas(
            origem="delta_sleep",
            filtro={"metadados.agent_id": agent_id},
        )
        
        # Agrupar por task_type e consolidar
        task_groups: Dict[str, List[Dict]] = {}
        for tarefa in tarefas:
            task_type = tarefa.get("task_type", "general")
            if task_type not in task_groups:
                task_groups[task_type] = []
            task_groups[task_type].append(tarefa)
        
        # Registrar sumário no vault
        summary = {
            "agent_id": agent_id,
            "total_tarefas": len(tarefas),
            "tipos_consolidados": list(task_groups.keys()),
            "status": "compactado",
        }
        
        self.subconscious.registrar_tarefa(
            origem="delta_sleep",
            tipo="summary",
            metadados=summary,
        )
        
        return summary

    async def sincronizar_delta_rem(self, fugue_compartment) -> Dict[str, Any]:
        """Sincroniza ciclo REM→Delta→REM com o FugueCompartment."""
        # Limpeza de toxinas
        limpeza_result = await self.limpar_toxinas()
        
        # Compactação de agentes ativos
        agents = await fugue_compartment._list_active_agents()
        compactacoes = []
        for agent_id in agents:
            result = self.compactar_memoria(agent_id)
            compactacoes.append(result)
        
        return {
            "limpeza": limpeza_result,
            "compactacoes": compactacoes,
        }

    async def _list_active_agents(self) -> List[str]:
        """Lista agentes ativos (método auxiliar)."""
        tarefas = self.subconscious.buscar_tarefas(
            origem="fugue_compartment",
            filtro={"status": "processing"},
        )
        return list({task["metadados"]["agent_id"] for task in tarefas})