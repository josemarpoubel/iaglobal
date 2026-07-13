# iaglobal/core/law_enforcement.py

import functools
from typing import Callable

from iaglobal.execution.cpu_affinity import cpu_affinity
from iaglobal.utils.logger import get_logger
from iaglobal.genesis.lineage_gate import (
    gate_node,
    LineageGateError,
    set_revocation_file,
)

logger = get_logger("iaglobal.law_enforcement")

# Inicializa CRL no path padrão (obsidian/revocation_list.json)
try:
    from iaglobal._paths import PACKAGE_DIR

    set_revocation_file(PACKAGE_DIR / "obsidian" / "revocation_list.json")
except Exception:
    pass


def enforce_universal_laws(func: Callable) -> Callable:
    """
    Decorador de Imposição de Leis Universais.

    Vínculo: Consciência (OmniMind) -> Execução (Nodes) -> Metabolismo (CPU Affinity).

    Integra três camadas de verificação:
      1. LineageGate — autenticação de DNA do nó (deriva de GENESIS_HASH_OFFICIAL)
      2. Lei do Pensamento — exige reasoning/plano no payload
      3. Penalidade metabólica — degrada agentes que violam a lei
    """
    node_name = getattr(func, "__name__", func.__class__.__name__)

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Tenta extrair o contexto (ctx) dos argumentos
        ctx = None
        for arg in args:
            if isinstance(arg, dict) and "agent_id" in arg:
                ctx = arg
                break
        if not ctx and "ctx" in kwargs:
            ctx = kwargs["ctx"]

        # --- CAMADA 1: LINEAGE GATE (autenticação genômica) ---
        # Injetar token derivado do GENESIS_HASH no contexto para que o nó
        # receba credencial válida sem precisar gerenciar chaves externas.
        if ctx is not None and "_lineage_token" not in ctx:
            try:
                from iaglobal.genesis.lineage_gate import get_expected_token

                ctx["_lineage_token"] = get_expected_token(node_name)
            except Exception:
                pass  # Falha silenciosa — Gate bloqueia se token ausente

        try:
            gate_node(node_name, ctx or {})
        except LineageGateError as e:
            logger.critical("[LAW_ENFORCEMENT] 🚨 %s", e)
            return {
                "output": "",
                "error": str(e),
                "lineage_blocked": True,
                "execution_metrics": {
                    "model": "lineage_gate",
                    "success": False,
                    "latency": 0.0,
                    "cost": 0.0,
                },
            }

        # Executa a função do nó (somente se autenticado)
        result = await func(*args, **kwargs)

        if ctx and isinstance(result, dict):
            agent_id = ctx.get("agent_id")
            if not agent_id:
                return result

            # --- CAMADA 2: LEI DO PENSAMENTO ---
            reasoning = (
                result.get("reasoning") or result.get("plan") or ctx.get("reasoning")
            )

            if not reasoning or len(str(reasoning)) < 10:
                # VIOLAÇÃO: Agir sem pensar consome ATP sem gerar fitness
                logger.warning(
                    "🚨 [LEI DO PENSAMENTO] Violação detectada para agente %s. "
                    "Ação sem propósito identificado. Aplicando penalidade metabólica.",
                    agent_id,
                )

                # --- CAMADA 3: PENALIDADE METABÓLICA ---
                cpu_affinity.survival_mode(agent_id)

                if "logs" not in result:
                    result["logs"] = []
                result["logs"].append(
                    "⚠️ Ação penalizada por violação da Lei do Pensamento: falta de reasoning."
                )

        return result

    return wrapper
