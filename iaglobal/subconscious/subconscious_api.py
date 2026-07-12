# iaglobal/subconscious/subconscious_api.py
"""SubconsciousAPI — Integração real com Obsidian Vault.

Responsabilidades:
- Registrar tarefas como notas no vault.
- Buscar tarefas via SmartQuery.
- Compactar/remover notas obsoletas.

Estrutura típica de uma nota no vault:
```
---
origem: fugue_compartment
tipo: critical
agent_id: agent_123
fugue_id: fugue_agent_123_critical
status: processing
metadados:
  chave: valor
---
Conteúdo da tarefa...
```
"""

# iaglobal/subconscious/subconscious_api.py
"""SubconsciousAPI — Wrapper para operações no Obsidian Vault via subconsciousapi.py.

Responsabilidades:
- Registrar tarefas no vault via subtarefas no `03_Long_Term`.
- Integrar com REMSleepEngine para consolidação.
- Fornecer interface para FugueCompartment e DeltaSleepSync.
"""

from typing import Any, Dict, List
from pathlib import Path
from iaglobal.obsidian.subconsciousapi import SubconsciousAPI as ObsidianSubconscious


class SubconsciousAPI:
    """API para operações no vault Obsidian."""

    def __init__(self):
        self.vault = ObsidianSubconscious()
        from iaglobal._paths import PACKAGE_DIR
        self.vault_path = PACKAGE_DIR / "obsidian" / "03_Long_Term" / "FugueTasks"

    async def registrar_tarefa(
        self,
        origem: str,
        tipo: str,
        metadados: Dict[str, Any],
    ) -> str:
        """Registra uma tarefa no vault."""
        nota = f"""---
id: {metadados.get('fugue_id', f'{origem}_{tipo}')}
origem: {origem}
tipo: {tipo}
tags: ["fugue", "subconscious"]
---

# {tipo}

**Agent:** {metadados.get('agent_id')}
**Status:** {metadados.get('status')}

```json
{metadados}
```
"""
        await self.vault.escrever_longo_prazo(
            nome=metadados.get("fugue_id", f"{origem}_{tipo}"),
            conteudo=nota,
            tipo=tipo,
            tags=["fugue", "subconscious"],
        )
        task_id = metadados.get("fugue_id", f"{origem}_{tipo}")
        return task_id

    async def buscar_tarefas(
        self, origem: str, filtro: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Busca tarefas no vault usando filtros."""
        query = [f"#{k}:{v}" for k, v in filtro.items()]
        query.append(f"origem:\"{origem}\"")
        notas = await self.vault.buscar_notas(" ".join(query))
        return [
            {
                "task_id": nota["id"],
                "origem": nota.get("origem"),
                "tipo": nota.get("tipo"),
                "metadados": nota.get("metadados", {}),
            }
            for nota in notas
        ]

    async def atualizar_tarefa(
        self, task_id: str, metadados: Dict[str, Any]
    ) -> bool:
        """Atualiza uma tarefa existente."""
        nota = await self.vault.ler_nota(task_id)
        if not nota:
            return False
        
        nota["metadados"].update(metadados)
        await self.vault.atualizar_nota(task_id, **nota)
        return True

    async def remover_tarefa(self, task_id: str) -> bool:
        """Remove uma tarefa do vault."""
        return await self.vault.remover_nota(task_id)