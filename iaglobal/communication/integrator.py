# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ColonyIntegrator — Junta resultados parciais em artefato final
e alimenta evolução + obsidian para continuidade evolutiva.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from iaglobal._paths import PROJECT_ROOT
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.communication.integrator")

OBSIDIAN_VAULT = Path(PROJECT_ROOT) / "iaglobal" / "obsidian"
OBSIDIAN_LONG_TERM = OBSIDIAN_VAULT / "03_Long_Term"


class ColonyIntegrator:
    """Integra resultados parciais em artefato final e alimenta aprendizado."""

    async def integrate(self, task_id: str, results: list[dict]) -> dict:
        """Combina N resultados parciais em um artefato final consolidado."""
        if not results:
            return {"task_id": task_id, "success": False, "error": "Nenhum resultado para integrar"}

        outputs = [r.get("result", r) for r in results]
        successes = [r.get("success", True) for r in results]
        all_ok = all(successes)
        total_latency = sum(r.get("latency_ms", 0) for r in results)

        integrated = {
            "task_id": task_id,
            "success": all_ok,
            "total_latency_ms": round(total_latency, 2),
            "num_workers": len(results),
            "outputs": outputs,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        logger.info("[INTEGRATOR] Integrado %s: %d workers, all_ok=%s, latency=%.0fms",
                    task_id, len(results), all_ok, total_latency)
        return integrated

    async def feed_evolution(self, task_id: str, final_result: dict):
        """Registra aprendizado no engine de evolução."""
        try:
            from iaglobal.evolution.meta_evolver import MetaEvolver

            evolver = MetaEvolver()
            await evolver.record_outcome(
                task_id=task_id,
                success=final_result.get("success", False),
                metrics={
                    "latency_ms": final_result.get("total_latency_ms", 0),
                    "num_workers": final_result.get("num_workers", 1),
                    "colony": True,
                },
            )
            logger.info("[INTEGRATOR] Evolução alimentada: %s", task_id)
        except Exception as e:
            logger.warning("[INTEGRATOR] Falha ao alimentar evolução: %s", e)

    async def feed_obsidian(self, organism_id: str, result: dict):
        """Escreve resultado consolidado no vault Obsidian (03_Long_Term)."""
        try:
            OBSIDIAN_LONG_TERM.mkdir(parents=True, exist_ok=True)

            filename = f"colony_{organism_id}_{result.get('task_id', 'unknown')}.md"
            filepath = OBSIDIAN_LONG_TERM / filename

            content = self._format_obsidian_note(organism_id, result)
            await self._write_async(filepath, content)
            logger.info("[INTEGRATOR] Resultado escrito no Obsidian: %s", filepath)
        except Exception as e:
            logger.warning("[INTEGRATOR] Falha ao escrever no Obsidian: %s", e)

    @staticmethod
    def _format_obsidian_note(organism_id: str, result: dict) -> str:
        lines = [
            f"# 🧬 Colony Result — {organism_id}",
            f"",
            f"- **Task ID:** {result.get('task_id', 'unknown')}",
            f"- **Timestamp:** {result.get('timestamp', 'N/A')}",
            f"- **Success:** {'✅' if result.get('success') else '❌'}",
            f"- **Workers:** {result.get('num_workers', 0)}",
            f"- **Total Latency:** {result.get('total_latency_ms', 0)}ms",
            f"",
            f"## Outputs",
            f"",
        ]
        for i, output in enumerate(result.get("outputs", [])):
            if isinstance(output, dict):
                out_str = json.dumps(output, indent=2, ensure_ascii=False)
            else:
                out_str = str(output)
            lines.append(f"### Worker {i + 1}")
            lines.append("```")
            lines.append(out_str[:500])
            lines.append("```")
            lines.append("")

        lines.extend([
            "---",
            "*Gerado pelo ColonyIntegrator*",
        ])
        return "\n".join(lines)

    @staticmethod
    async def _write_async(path: Path, content: str):
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: path.write_text(content, encoding="utf-8"))