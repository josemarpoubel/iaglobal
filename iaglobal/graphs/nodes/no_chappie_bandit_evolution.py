# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.graphs.nodes.no_chappie_bandit_evolution")


async def run_chappie_bandit_evolution(ctx: dict) -> dict:
    try:
        from iaglobal.chappie.bandit_evolution import get_bandit_evolution

        bandit = get_bandit_evolution()
        result = await bandit.autonomous_cycle()
        logger.info(
            "[ChappieBandit] Ciclo evolutivo | providers=%d fitness_medio=%.3f",
            result.get("providers_analisados", 0),
            result.get("fitness_medio", 0.0),
        )
        return {
            "status": "ok",
            "evolution_metrics": result,
            "execution_metrics": {
                "success": True,
                "latency": 0.1,
                "cost": 0.0,
                "model": "chappie_bandit_evolution",
            },
        }
    except Exception as e:
        logger.error("[ChappieBandit] Erro no ciclo evolutivo: %s", e, exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "execution_metrics": {
                "success": False,
                "latency": 0.0,
                "cost": 0.0,
                "model": "chappie_bandit_evolution",
            },
        }
