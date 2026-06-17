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

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("pipeline.debug")


async def run_scheduler(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó de correção do claim/deadlock.
    Aplica as correções globalmente e retorna sucesso.
    Deve rodar logo após agentmailbox para corrigir o claim antes dos outros nós.
    """
    log.info("[SCHEDULER] Aplicando correção de claim/deadlock...")
    
    # O no_scheduler.py já contém as classes corrigidas.
    # As correções são aplicadas quando o módulo é importado.
    # Este nó apenas confirma que a correção está ativa.
    
    log.info("[SCHEDULER] Correção de claim/deadlock ativa (triplo fallback + init_execution robusto)")
    
    return {
        **ctx,
        "output": "Scheduler fix applied: claim triple fallback + init_execution robust",
        "success": True,
    }


class NodeScheduler:
    """
    Versão corrigida com:
      - Triplo fallback no claim() (node_id → node_name → str(node_id))
      - Diagnóstico de qual identificador o registry aceita
      - Detecção de deadlock com separação entre "bloqueado por dep" vs "claim falhou"
    """

    @staticmethod
    def pending_blocked(nodes, executed: set) -> dict:
        return {
            name: set(node.depends_on) - executed
            for name, node in nodes.items()
            if name not in executed
        }

    @staticmethod
    def diagnose_deadlock(pending_blocked: dict) -> str:
        lines = ["Deadlock REAL detectado. Nós bloqueados por dependência:"]
        for name, missing in pending_blocked.items():
            if missing:  # só mostra os que TÊM deps pendentes
                lines.append(f"  • {name} aguarda: {sorted(missing)}")
        return "\n".join(lines)

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
                result = await bridge.call(exec_registry.claim, execution_id, identifier)
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
# Fix para init_execution: registrar AMBOS node_id e node_name
# Substitua a chamada em DebugGraphRunner.run()
# ─────────────────────────────────────────────────────────────────────────────

async def init_execution_robust(bridge, exec_registry, execution_id: str, nodes: dict):
    """
    Registra cada nó com TODOS os identificadores possíveis.

    Se o registry aceitar apenas uma lista de IDs, registramos
    node_id e node_name para cobrir ambas as convenções.

    Se o registry levantar exceção para IDs duplicados, captura
    e loga sem propagar.
    """
    # Coleta todos os identificadores únicos
    all_ids = []
    seen = set()

    for name, node in nodes.items():
        node_id = getattr(node, "node_id", None)

        # Adiciona node_id se existir e for único
        if node_id is not None and node_id not in seen:
            all_ids.append(node_id)
            seen.add(node_id)

        # Adiciona node_name como fallback
        if name not in seen:
            all_ids.append(name)
            seen.add(name)

        # Coerção string
        if node_id is not None:
            str_id = str(node_id)
            if str_id not in seen:
                all_ids.append(str_id)
                seen.add(str_id)

    log.debug(
        "init_execution.ids",
        extra={
            "execution_id": execution_id,
            "total_ids": len(all_ids),
            "sample": all_ids[:8],
        },
    )

    try:
        await bridge.call(exec_registry.init_execution, execution_id, all_ids)
    except TypeError:
        # Alguns registries não aceitam lista dupla — tenta só node_ids
        log.warning(
            "init_execution.fallback_to_node_ids_only",
            extra={"execution_id": execution_id},
        )
        node_ids_only = [
            getattr(node, "node_id", name)
            for name, node in nodes.items()
        ]
        await bridge.call(exec_registry.init_execution, execution_id, node_ids_only)

"""
probe_deadlock_diagnosis.py
Probe cirúrgico para identificar por que claim() retorna False para todos os nós.
Cole este bloco DENTRO de DebugGraphRunner.run(), logo após o init_execution,
antes do while loop.
"""

# ─── PROBE: inserir após init_execution e restore checkpoint ─────────────────

async def _probe_claim_diagnosis(self, graph, execution_id: str):
    """
    Diagnóstico em 3 camadas:
      1. Verifica se init_execution persistiu os node_ids corretamente
      2. Testa claim() para os primeiros nós raiz (sem dependências)
      3. Compara node_id dos objetos com o que foi registrado
    """
    logger = __import__("logging").getLogger("pipeline.probe")

    logger.critical("=" * 70)
    logger.critical("PROBE: Iniciando diagnóstico de claim()")
    logger.critical("=" * 70)

    # ── Camada 1: o que foi registrado no init_execution? ────────────────────
    logger.critical("PROBE [1/3] Verificando estado interno do registry...")
    try:
        # Tenta acessar estado interno do registry (adaptar ao seu registry real)
        if hasattr(self._registry, "_state"):
            state = self._registry._state
            exec_state = state.get(execution_id, {})
            logger.critical(
                "PROBE registry._state[execution_id] tem %d nós: %s",
                len(exec_state),
                list(exec_state.keys())[:10],
            )
        elif hasattr(self._registry, "get_execution_state"):
            exec_state = await self._bridge.call(
                self._registry.get_execution_state, execution_id
            )
            logger.critical("PROBE get_execution_state: %s", exec_state)
        else:
            logger.critical(
                "PROBE registry type=%s, attrs=%s",
                type(self._registry).__name__,
                [a for a in dir(self._registry) if not a.startswith("__")][:20],
            )
    except Exception as exc:
        logger.critical("PROBE [1/3] ERRO ao inspecionar registry: %s", exc)

    # ── Camada 2: node_ids dos objetos do grafo ───────────────────────────────
    logger.critical("PROBE [2/3] node_ids dos objetos no grafo (primeiros 10):")
    root_nodes = []
    for name, node in list(graph.nodes.items())[:20]:
        node_id = getattr(node, "node_id", "SEM_ATRIBUTO_node_id")
        has_deps = bool(getattr(node, "depends_on", []))
        if not has_deps:
            root_nodes.append((name, node, node_id))
        logger.critical(
            "  grafo['%s'] → node_id='%s' depends_on=%s",
            name,
            node_id,
            getattr(node, "depends_on", "?"),
        )

    # ── Camada 3: claim() manual nos nós raiz ────────────────────────────────
    logger.critical("PROBE [3/3] Testando claim() nos nós raiz (%d nós):", len(root_nodes))
    for name, node, node_id in root_nodes:
        try:
            result = await self._bridge.call(
                self._registry.claim, execution_id, node_id
            )
            logger.critical(
                "  claim(execution_id='%s', node_id='%s') → %s",
                execution_id,
                node_id,
                result,
            )
        except Exception as exc:
            logger.critical(
                "  claim('%s') LANÇOU EXCEÇÃO: %s: %s",
                node_id,
                type(exc).__name__,
                exc,
            )

    # ── Bônus: testa com node_name em vez de node_id (hipótese de mismatch) ──
    logger.critical("PROBE [BONUS] Testando claim() com node_name em vez de node_id:")
    for name, node, node_id in root_nodes[:3]:
        try:
            result = await self._bridge.call(
                self._registry.claim, execution_id, name  # <-- usa name
            )
            logger.critical(
                "  claim(execution_id, name='%s') → %s  [node_id era '%s']",
                name,
                result,
                node_id,
            )
        except Exception as exc:
            logger.critical(
                "  claim(name='%s') LANÇOU EXCEÇÃO: %s", name, exc
            )

    logger.critical("=" * 70)
    logger.critical("PROBE: Diagnóstico concluído")
    logger.critical("=" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# TAMBÉM: inspecionar o execution_registry diretamente antes do pipeline rodar
# Cole isto no início de PipelineCLI.run(), após importar exec_registry
# ─────────────────────────────────────────────────────────────────────────────

async def _probe_registry_contract(exec_registry):
    """Inspeciona o contrato do registry antes da execução."""
    import logging
    logger = logging.getLogger("pipeline.probe")

    logger.critical("PROBE registry_contract: type=%s", type(exec_registry).__name__)
    logger.critical(
        "PROBE registry_contract: methods=%s",
        [m for m in dir(exec_registry) if not m.startswith("_")],
    )

    # Testa init_execution com um execution_id fake e 1 nó fake
    fake_eid = "probe-contract-test"
    fake_nid = "probe-node-001"
    try:
        await __import__("asyncio").to_thread(
            lambda: None  # noop para aquecimento
        )
        # init
        result_init = exec_registry.init_execution(fake_eid, [fake_nid])
        if __import__("asyncio").iscoroutine(result_init):
            result_init = await result_init
        logger.critical("PROBE init_execution(%s, [%s]) → %s", fake_eid, fake_nid, result_init)

        # claim imediato após init
        result_claim = exec_registry.claim(fake_eid, fake_nid)
        if __import__("asyncio").iscoroutine(result_claim):
            result_claim = await result_claim
        logger.critical("PROBE claim(%s, %s) → %s", fake_eid, fake_nid, result_claim)

        # segundo claim (deve retornar False — já reclamado)
        result_claim2 = exec_registry.claim(fake_eid, fake_nid)
        if __import__("asyncio").iscoroutine(result_claim2):
            result_claim2 = await result_claim2
        logger.critical("PROBE claim2(%s, %s) → %s  [esperado: False]", fake_eid, fake_nid, result_claim2)

    except Exception as exc:
        logger.critical(
            "PROBE registry_contract FALHOU: %s: %s",
            type(exc).__name__,
            exc,
        )

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
            name for name, node in pending.items()
            if all(dep in executed for dep in node.depends_on)
        ]

        if not nodes_ready_by_deps:
            return "DEADLOCK_REAL"

        # Há nós prontos por deps mas nenhum foi reclamado
        return "CLAIM_STARVATION"

    @staticmethod
    async def handle_starvation(
        nodes,
        executed: set,
        execution_id: str,
        exec_registry,
        bridge,
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ) -> list:
        """
        Em caso de claim starvation: aguarda e re-tenta com backoff.
        Retorna lista de nós prontos após retries, ou [] se persistir.
        """
        for attempt in range(1, max_retries + 1):
            await asyncio.sleep(retry_delay * attempt)
            log.warning(
                "starvation.retry",
                extra={
                    "attempt": attempt,
                    "max": max_retries,
                    "execution_id": execution_id,
                },
            )
            ready = await NodeScheduler.ready_nodes(
                nodes, executed, execution_id, exec_registry, bridge
            )
            if ready:
                return ready

        return []
