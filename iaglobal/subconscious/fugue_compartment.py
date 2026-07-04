# iaglobal/subconscious/fugue_compartment.py
"""Compartimento de Fuga (Fugue Compartment) — Processamento subconsciente de tarefas.

Objetivo:
- Processar tarefas críticas em segundo plano.
- Integrar com SubconsciousAPI para registro no vault.
- Evitar bloqueio do pipeline consciente.
- Permitir busca de "tarefas de fuga" via metadados.
"""

import asyncio
import time
from typing import Any, Dict, Optional
from iaglobal.subconscious.subconscious_api import SubconsciousAPI
from iaglobal.subconscious.delta_sleep import DeltaSleepSync


class FugueCompartment:
    """Módulo para processamento de tarefas em segundo plano."""

    def __init__(self):
        self.subconscious = SubconsciousAPI()
        self.delta_sleep = DeltaSleepSync()
        self._background_tasks: Dict[str, Dict] = {}
        
        # Ciclo de sincronização será iniciado manualmente em ambiente de produção

    async def processar_em_segundo_plano(
        self,
        agent_id: str,
        task_data: Dict[str, Any],
        task_type: str,
    ) -> str:
        """Processa uma tarefa em segundo plano e registra no vault."""
        fugue_id = f"fugue_{agent_id}_{task_type}"
        
        # Armazenar tarefa para referência futura
        self._background_tasks[fugue_id] = {
            "agent_id": agent_id,
            "task_data": task_data,
            "task_type": task_type,
            "status": "processing",
        }
        
        # Registrar no vault via SubconsciousAPI
        await self.subconscious.registrar_tarefa(
            origem="fugue_compartment",
            tipo=task_type,
            metadados={
                "agent_id": agent_id,
                "fugue_id": fugue_id,
                "task_type": task_type,
                "status": "processing",
                "timestamp": time.time(),
                "contexto": task_data,
            },
        )
        
        # Simular processamento (async)
        await self._simular_processamento(fugue_id)
        
        return fugue_id

    async def _simular_processamento(self, fugue_id: str) -> None:
        """Simula processamento assíncrono de uma tarefa."""
        import asyncio
        await asyncio.sleep(1)  # Simula carga de trabalho
        
        # Atualizar status
        task = self._background_tasks.get(fugue_id)
        if task:
            task["status"] = "completed"
            await self.subconscious.atualizar_tarefa(
                origem="fugue_compartment",
                task_id=fugue_id,
                metadados={"status": "completed"},
            )

    async def buscar_tarefas_por_tipo(self, task_type: str) -> list[Dict[str, Any]]:
        """Busca tarefas de fuga por tipo (via metadados no vault)."""
        return await self.subconscious.buscar_tarefas(
            origem="fugue_compartment",
            filtro={"task_type": task_type},
        )

    async def get_status(self, fugue_id: str) -> Optional[str]:
        """Retorna o status de uma tarefa de fuga."""
        task = self._background_tasks.get(fugue_id)
        return task["status"] if task else None

    async def _delta_sync_cycle(self) -> None:
        """Ciclo contínuo de sincronização REM→Delta→REM."""
        while True:
            await asyncio.sleep(3600)  # Executa a cada 1 hora
            await self.delta_sleep.sincronizar_delta_rem(self)
            
    async def _list_active_agents(self) -> list[str]:
        """Lista agentes com tarefas ativas (para DeltaSleepSync)."""
        return list({
            task["agent_id"] for task in self._background_tasks.values()
            if task["status"] == "processing"
        })