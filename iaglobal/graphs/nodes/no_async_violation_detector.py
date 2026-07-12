# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_async_violation_detector.py

from typing import Any, Dict

from iaglobal.immunity.async_violation_detector import async_violation_detector


async def run_async_violation_detector(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Executor: escaneia o ecossistema em busca de violações async."""
    try:
        target_dirs = ctx.get("target_dirs") or ["iaglobal", "scripts"]
        result = await async_violation_detector.scan_ecosystem(target_dirs)
        return {
            "output": result,
            "async_violation_detector": result,
            "success": True,
            "execution_metrics": {
                "success": True,
                "latency": result.get("latency_ms", 0) / 1000,
                "cost": 0.0,
                "model": "native-scanner",
            },
        }
    except Exception as e:
        return {
            "output": {"error": str(e)},
            "async_violation_detector": {"error": str(e)},
            "success": False,
            "execution_metrics": {
                "success": False,
                "latency": 0.0,
                "cost": 0.0,
                "model": "native-scanner",
            },
        }
