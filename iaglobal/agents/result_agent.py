# iaglobal/agents/result_agent.py

from iaglobal.utils.logger import logger


class ResultAgent:
    """Agrega saídas de todos os agentes e formata a resposta final."""

    def build_result(self, ctx: dict) -> dict:
        logger.info("📋 [RESULT] Compilando resultado final...")

        documentation = ctx.get("documentation", {})
        release = ctx.get("release", {})
        metrics = ctx.get("metrics", {})
        optimization = ctx.get("optimization", {})

        summary_parts = []

        if isinstance(documentation, dict):
            readme = documentation.get("readme", "")
            if readme:
                summary_parts.append("Documentação gerada")
        elif documentation:
            summary_parts.append("Documentação disponível")

        if isinstance(release, dict):
            changelog = release.get("changelog", "")
            if changelog:
                summary_parts.append(f"Changelog: {changelog[:100]}...")
        elif release:
            summary_parts.append("Release notes disponíveis")

        if isinstance(metrics, dict):
            durations = metrics.get("durations", {})
            quality = metrics.get("quality_scores", {})
            if durations:
                total = sum(durations.values()) if isinstance(durations, dict) else 0
                summary_parts.append(f"Tempo total: {total:.1f}s")
            if quality:
                avg = sum(quality.values()) / len(quality) if isinstance(quality, dict) and quality else 0
                summary_parts.append(f"Qualidade média: {avg:.2f}")

        if isinstance(optimization, dict):
            patterns = optimization.get("patterns", [])
            if patterns:
                summary_parts.append(f"{len(patterns)} padrões de otimização identificados")

        summary = ". ".join(summary_parts) if summary_parts else "Pipeline concluída."
        next_steps = ["Revisar artefatos gerados", "Executar testes manuais", "Implantar em staging"]

        return {
            "final_result": {
                "status": "concluído",
                "artifacts": {
                    "documentation": bool(documentation),
                    "release": bool(release),
                    "metrics": bool(metrics),
                },
            },
            "summary": summary,
            "next_steps": next_steps,
        }
