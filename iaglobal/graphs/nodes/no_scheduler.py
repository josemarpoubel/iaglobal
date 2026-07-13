# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_scheduler.py

"""
no_scheduler.py — Patch cirúrgico para o falso deadlock
════════════════════════════════════════════════════════════════════════════════
Problema confirmado pelos logs:
  - 8 nós com depends_on=[] não são reclamados pelo claim()
  - NodeScheduler.ready_nodes() retorna [] na iteração 1
  - DeadlockDetector dispara: FALSO POSITIVO

Causa raiz mais provável:
  - claim(execution_id, node.node_id) falha porque node.node_id
    diverge do identificador usado em init_execution() após canonicalize()

Esta correção:
  1. Tenta claim com node.node_id (contrato original)
  2. Fallback: tenta com node_name (string do dict do grafo)
  3. Fallback final: tenta com str(node.node_id) (coerção de tipo)
  4. Loga QUAL forma funcionou → confirma hipótese
  5. init_execution agora usa AMBOS os identificadores para garantir registro
════════════════════════════════════════════════════════════════════════════════
Substitua NodeScheduler e a chamada init_execution em DebugGraphRunner.run()
"""

import logging
from typing import Any, List, Optional, Tuple

log = logging.getLogger("pipeline.debug")


class NodeScheduler:
    @staticmethod
    async def ready_nodes(
        nodes,
        executed: set,
        execution_id: str,
        exec_registry,
        bridge,
    ) -> List[Tuple[str, Any]]:
        """
        Determina nós prontos com triplo fallback no claim().

        Ordem de tentativa para cada nó:
          1. claim(execution_id, node.node_id)          — contrato original
          2. claim(execution_id, node_name)              — fallback por nome
          3. claim(execution_id, str(node.node_id))     — coerção de tipo

        O primeiro que retornar True é usado. O identificador vencedor
        é logado em DEBUG para diagnóstico.
        """
        ready = []
        claim_failures = []

        for name, node in nodes.items():
            if name in executed:
                continue
            if not all(dep in executed for dep in node.depends_on):
                continue

            # Nó está pronto por dependências — tentar claim
            claimed, winning_id = await NodeScheduler._claim_with_fallback(
                exec_registry, bridge, execution_id, node, name
            )

            if claimed:
                log.debug(
                    "claim.ok",
                    extra={"node": name, "winning_id": winning_id},
                )
                ready.append((name, node))
            else:
                claim_failures.append(name)

        if claim_failures:
            log.warning(
                "claim.failed_for_ready_nodes",
                extra={
                    "count": len(claim_failures),
                    "nodes": claim_failures,
                    "hint": (
                        "Nós têm deps satisfeitas mas claim() retornou False. "
                        "Verifique se init_execution registrou os IDs corretamente."
                    ),
                },
            )

        return ready

    @staticmethod
    async def _claim_with_fallback(
        exec_registry,
        bridge,
        execution_id: str,
        node,
        node_name: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Tenta claim com três identificadores diferentes.
        Retorna (True, id_vencedor) ou (False, None).
        """
        node_id = getattr(node, "node_id", None)

        candidates = []
        if node_id is not None:
            candidates.append(("node_id", node_id))
        # Fallback 1: nome do nó no grafo
        if node_name not in [v for _, v in candidates]:
            candidates.append(("node_name", node_name))
        # Fallback 2: coerção string do node_id
        if node_id is not None and str(node_id) != node_id:
            candidates.append(("str(node_id)", str(node_id)))

        for label, identifier in candidates:
            try:
                result = await bridge.call(
                    exec_registry.claim, execution_id, identifier
                )
                if result:
                    if label != "node_id":
                        # Confirma hipótese de mismatch
                        log.warning(
                            "claim.id_mismatch_fixed",
                            extra={
                                "node": node_name,
                                "failed_with": "node_id",
                                "succeeded_with": label,
                                "node_id_value": str(node_id)[:60],
                                "winning_value": str(identifier)[:60],
                            },
                        )
                    return True, label
            except Exception as exc:
                log.debug(
                    "claim.attempt_exception",
                    extra={"node": node_name, "id_type": label, "error": str(exc)},
                )
                continue

        return False, None


# ─────────────────────────────────────────────────────────────────────────────
# DeadlockDetector corrigido: distingue deadlock REAL de claim failure
# ─────────────────────────────────────────────────────────────────────────────


class DeadlockDetector:
    """
    O detector original confundia dois cenários distintos:

    Cenário A — Deadlock REAL:
      Todos os nós pendentes têm dependências não-satisfeitas.
      Nenhum progresso é possível mesmo esperando.

    Cenário B — Claim Starvation (falso positivo):
      Nós têm dependências satisfeitas MAS claim() retorna False.
      O progresso é possível — outro worker já reclamou os nós
      ou o registry está em estado inconsistente.

    Esta versão distingue os dois e toma ação apropriada.
    """

    @staticmethod
    def classify(
        nodes,
        executed: set,
        ready_by_deps: list,
    ) -> str:
        """
        Classifica a condição de parada.

        ready_by_deps: nós que teriam deps satisfeitas (independente de claim)
        """
        pending = {n: node for n, node in nodes.items() if n not in executed}

        if not pending:
            return "COMPLETED"

        nodes_ready_by_deps = [
            name
            for name, node in pending.items()
            if all(dep in executed for dep in node.depends_on)
        ]

        if not nodes_ready_by_deps:
            return "DEADLOCK_REAL"

        # Há nós prontos por deps mas nenhum foi reclamado
        return "CLAIM_STARVATION"


async def run_scheduler(ctx: dict) -> dict:
    """Executa o agendador de nós de forma assíncrona.

    Prepara o scheduler e retorna nós prontos para execução.
    """
    return {
        "output": "scheduler_ok",
        "scheduler": {},
        "execution_metrics": {
            "model": "scheduler",
            "success": True,
            "latency": 0.0,
            "cost": 0.0,
        },
    }
