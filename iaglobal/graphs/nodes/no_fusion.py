# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_fusion.py

"""
Fusion node — Propõe e executa fusão de agentes via FusionEngine.

Este nó:
1. Identifica candidatos à fusão (agentes com ressonância ≥ 0.6)
2. Calcula ressonância de DNA entre candidatos
3. Executa fusão se viável
4. Registra linhagem no Obsidian (AncestryTree)

Integração:
- FusionEngine: iaglobal.evolution.fusion_engine
- Obsidian: iaglobal.obsidian.subconsciousapi (registro de linhagem)
- EvolutionCommittee: Pode ser acionado após fusão para validar híbrido
"""

import time
import logging
import asyncio
from typing import Dict, Any, List, Optional

from iaglobal.evolution.fusion_engine import fusion_engine, FusionResult
from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
from iaglobal.obsidian.omnimind import omni_mind

logger = logging.getLogger(__name__)


async def _identify_fusion_candidates(ctx: Dict[str, Any]) -> List[str]:
    """
    Identifica agentes candidatos à fusão baseado no contexto.

    Critérios:
    - Agentes com fitness > 0.7
    - Agentes que cooperaram recentemente (SymbiosisScore)
    - Agentes com traits complementares

    Returns:
        Lista de agent_ids candidatos
    """
    # Obter agentes do contexto (se disponíveis)
    available_agents = ctx.get("available_agents", [])

    if not available_agents:
        # Fallback: usar agentes registrados no DNA
        available_agents = list(fusion_engine._agent_dnas.keys())

    # Filtrar por fitness (se informação disponível)
    candidates = []
    for agent_id in available_agents:
        dna = fusion_engine._agent_dnas.get(agent_id)
        if dna and dna.fitness_score >= 0.7:
            candidates.append(agent_id)

    # Se poucos candidatos, incluir todos com fitness > 0.5
    if len(candidates) < 2:
        for agent_id in available_agents:
            dna = fusion_engine._agent_dnas.get(agent_id)
            if dna and dna.fitness_score >= 0.5 and agent_id not in candidates:
                candidates.append(agent_id)

    return candidates[:4]  # Máximo 4 candidatos


async def _calculate_pairwise_resonance(
    candidate_ids: List[str],
) -> List[tuple[str, str, float]]:
    """
    Calcula ressonância entre todos os pares de candidatos.

    Returns:
        Lista de (agent_a, agent_b, resonance_score) ordenada por score
    """
    pairs = []

    for i, agent_a in enumerate(candidate_ids):
        for agent_b in candidate_ids[i + 1 :]:
            res = await asyncio.to_thread(
                fusion_engine.calculate_dna_resonance,
                agent_a,
                agent_b,
            )

            if res.get("compatible", False):
                pairs.append((agent_a, agent_b, res["resonance_score"]))

    # Ordenar por ressonância (maior primeiro)
    pairs.sort(key=lambda x: x[2], reverse=True)

    return pairs


async def _execute_fusion(
    parent_ids: List[str],
    hybrid_name: str,
    ctx: Dict[str, Any],
) -> FusionResult:
    """Executa fusão de agentes."""
    result = await fusion_engine.fuse_agents_async(
        parent_ids=parent_ids,
        hybrid_name=hybrid_name,
        force=False,  # Respeita threshold
    )

    return result


async def _register_lineage_obsidian(
    hybrid_id: str,
    parents: List[str],
    resonance_score: float,
) -> Optional[str]:
    """Registra linhagem no Obsidian."""
    try:
        subconscious = SubconsciousAPI()

        parents_str = ", ".join(parents)
        note_content = (
            f"**Híbrido**: {hybrid_id}\n"
            f"**Pais**: {parents_str}\n"
            f"**Ressonância**: {resonance_score:.2f}\n"
            f"**Geração**: {fusion_engine._agent_dnas[hybrid_id].generation if hybrid_id in fusion_engine._agent_dnas else 'N/A'}\n"
            f"**Timestamp**: {time.time()}\n"
        )

        note_id = await subconscious.escrever_longo_prazo(
            f"fusion_lineage_{hybrid_id}_{int(time.time())}",
            note_content,
            tags=[
                "#fusion",
                "#lineage",
                "#hybrid",
                f"#gen-{fusion_engine._agent_dnas[hybrid_id].generation if hybrid_id in fusion_engine._agent_dnas else '0'}",
            ],
        )

        # Registrar no FusionEngine
        await fusion_engine.register_lineage_async(
            hybrid_id=hybrid_id,
            parents=parents,
            obsidian_note_id=note_id,
        )

        logger.info("[FUSION] Linhagem registrada no Obsidian: %s", note_id)
        return note_id

    except Exception as e:
        logger.error("[FUSION] Erro ao registrar linhagem: %s", e)
        return None


async def run_fusion(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó de fusão de agentes.

    Fluxo:
    1. Identifica candidatos
    2. Calcula ressonância entre pares
    3. Executa fusão do par com maior ressonância
    4. Registra linhagem no Obsidian
    5. Retorna resultado

    Input (ctx):
        - available_agents: Lista de agent_ids disponíveis (opcional)
        - force_fusion: Se True, força fusão mesmo com ressonância baixa
        - max_candidates: Máximo de candidatos a considerar (default: 4)

    Output:
        - fusion_result: FusionResult (success, hybrid_id, etc)
        - candidates_analyzed: Quantidade de candidatos analisados
        - pairs_evaluated: Quantidade de pares avaliados
        - obsidian_note_id: ID da nota de linhagem (se registrado)
    """
    start_time = time.time()

    # Consultar OmniMind para orientação existencial
    try:
        orientacao = omni_mind.consultar(
            agent_id="fusion_node",
            pergunta="Devo proceder com fusão de agentes para evoluir o ecossistema?",
            contexto={"available_agents": ctx.get("available_agents", [])},
        )
        logger.debug(
            "[FUSION] Orientação OmniMind: %s",
            orientacao.guidance[:100] if orientacao else "N/A",
        )
    except Exception as e:
        logger.debug("[FUSION] Erro ao consultar OmniMind: %s", e)

    # 1. Identificar candidatos
    candidates = await _identify_fusion_candidates(ctx)

    if len(candidates) < 2:
        logger.warning(
            "[FUSION] Poucos candidatos (%d). Fusão não executada.", len(candidates)
        )
        return {
            "fusion_result": None,
            "candidates_analyzed": len(candidates),
            "pairs_evaluated": 0,
            "reason": "insufficient_candidates",
            "execution_metrics": {
                "model": "fusion_engine",
                "success": False,
                "latency": (time.time() - start_time) * 1000.0,
                "cost": 0.0,
            },
        }

    logger.info("[FUSION] %d candidatos identificados: %s", len(candidates), candidates)

    # 2. Calcular ressonância entre pares
    pairs = await _calculate_pairwise_resonance(candidates)

    if not pairs:
        logger.warning("[FUSION] Nenhum par compatível encontrado.")
        return {
            "fusion_result": None,
            "candidates_analyzed": len(candidates),
            "pairs_evaluated": 0,
            "reason": "no_compatible_pairs",
            "execution_metrics": {
                "model": "fusion_engine",
                "success": False,
                "latency": (time.time() - start_time) * 1000.0,
                "cost": 0.0,
            },
        }

    logger.info(
        "[FUSION] %d pares compatíveis encontrados. Melhor ressonância: %.2f",
        len(pairs),
        pairs[0][2],
    )

    # 3. Executar fusão do par com maior ressonância
    best_pair = pairs[0]
    agent_a, agent_b, resonance = best_pair

    hybrid_name = f"hybrid_{agent_a[:8]}_{agent_b[:8]}_{int(time.time())}"

    # Verificar se deve forçar fusão
    force_fusion = ctx.get("force_fusion", False)

    logger.info(
        "[FUSION] Executando fusão: %s + %s → %s", agent_a, agent_b, hybrid_name
    )

    fusion_result = await _execute_fusion(
        parent_ids=[agent_a, agent_b],
        hybrid_name=hybrid_name,
        ctx=ctx,
    )

    # 4. Registrar linhagem no Obsidian (se sucesso)
    obsidian_note_id = None
    if fusion_result.success:
        obsidian_note_id = await _register_lineage_obsidian(
            hybrid_id=hybrid_name,
            parents=[agent_a, agent_b],
            resonance_score=resonance,
        )

        logger.info(
            "[FUSION] ✅ Fusão bem-sucedida: %s (ressonância=%.2f, viabilidade=%.2f)",
            hybrid_name,
            resonance,
            fusion_result.viability_score,
        )
    else:
        logger.warning(
            "[FUSION] ❌ Fusão falhou: %s (erro=%s)",
            hybrid_name,
            fusion_result.errors[0] if fusion_result.errors else "unknown",
        )

    # 5. Retornar resultado
    latency_ms = (time.time() - start_time) * 1000.0

    return {
        "fusion_result": {
            "success": fusion_result.success,
            "hybrid_id": fusion_result.hybrid_id,
            "parents": fusion_result.parents,
            "resonance_score": fusion_result.resonance_score,
            "viability_score": fusion_result.viability_score,
            "errors": fusion_result.errors,
            "warnings": fusion_result.warnings,
        },
        "candidates_analyzed": len(candidates),
        "pairs_evaluated": len(pairs),
        "best_pair": {"agent_a": agent_a, "agent_b": agent_b, "resonance": resonance},
        "obsidian_note_id": obsidian_note_id,
        "execution_metrics": {
            "model": "fusion_engine",
            "success": fusion_result.success,
            "latency": latency_ms,
            "cost": ctx.get("estimated_cost", 0.05),  # Fusão é mais cara
        },
    }
