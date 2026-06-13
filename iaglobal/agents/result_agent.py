# iaglobal/agents/result_agent.py

from __future__ import annotations

import hashlib

import logging

from dataclasses import dataclass, asdict

from datetime import datetime, timezone

from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from iaglobal.utils.logger import get_logger

logger = logging.getLogger(__name__)

# ============================================================
# DOMAIN CONTRACTS
# ============================================================

@dataclass(slots=True)
class PipelineHealth:
    total_agents: int
    successful_agents: int
    failed_agents: int
    success_rate: float


@dataclass(slots=True)
class FinalPayload:
    status: str
    artifacts_present: Dict[str, bool]
    payload: Any
    checksum: str


@dataclass(slots=True)
class ResultContract:
    version: str
    timestamp: str
    execution_id: Optional[str]
    final_result: Dict[str, Any]
    summary: str
    next_steps: List[str]
    health: Dict[str, Any]


# ============================================================
# RESULT AGENT
# ============================================================

class ResultAgent:
    """
    Terminal Sink Node responsável por:

    - Consolidação multi-agente
    - Higienização de contexto
    - Health Check da pipeline
    - Contrato determinístico de saída
    - Auto-Healing de dados inconsistentes
    - Observabilidade
    - Evolução OCP-ready
    """

    CONTRACT_VERSION = "3.0.0"

    def __init__(self):

        self._summary_extractors = {
            "documentation": self._extract_docs_summary,
            "release": self._extract_release_summary,
            "metrics": self._extract_metrics_summary,
            "optimization": self._extract_optimization_summary,
            "coder": self._extract_code_summary,
            "security_audit": self._extract_security_summary,
        }

        self._summary_extractors.update({
            "planner": self._extract_generic_summary,
            "search": self._extract_generic_summary,
            "review": self._extract_generic_summary,
            "multi_coder": self._extract_code_summary,
            "critic": self._extract_generic_summary,
            "validator": self._extract_generic_summary,
            "ast_validator": self._extract_generic_summary,
            "security": self._extract_security_summary,
        })

    def _extract_generic_summary(
        self,
        data: Any
    ):

        try:

            if isinstance(data, dict):

                output = data.get("output")

                if output:

                    return (
                        f"dados produzidos por {type(output).__name__}",
                        []
                    )

            return (
                "resultado disponível",
                []
            )

        except Exception:

            return (
                "resultado disponível",
                []
            )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def build_result(
        self,
        ctx: Dict[str, Any]
    ) -> Dict[str, Any]:

        logger.info(
            "[RESULT_AGENT] Building Final Execution Contract..."
        )

        summary_parts: List[str] = []

        artifacts_status: Dict[str, bool] = {}

        dynamic_next_steps: Set[str] = set()

        successful_agents = 0
        failed_agents = 0

        # ====================================================
        # SAFE EXTRACTION LOOP
        # ====================================================

        for agent_name, extractor in self._summary_extractors.items():

            agent_data = ctx.get(agent_name)

            has_data = bool(agent_data)

            artifacts_status[agent_name] = has_data

            if not has_data:
                failed_agents += 1
                continue

            try:

                summary, next_steps = extractor(agent_data)

                successful_agents += 1

                if summary:
                    summary_parts.append(summary)

                dynamic_next_steps.update(next_steps)

            except Exception as exc:

                failed_agents += 1

                logger.exception(
                    "Extractor failure [%s]: %s",
                    agent_name,
                    exc
                )

                summary_parts.append(
                    f"{agent_name}: extractor failure"
                )

        # ====================================================
        # AUTO-HEALING
        # ====================================================

        if not dynamic_next_steps:

            dynamic_next_steps.update(
                {
                    "Review generated artifacts",
                    "Execute local validation",
                    "Run integration tests",
                }
            )

        final_summary = (
            " | ".join(summary_parts)
            if summary_parts
            else "Pipeline completed successfully."
        )

        # ====================================================
        # PAYLOAD RESOLUTION
        # ====================================================

        main_payload = self._resolve_main_payload(ctx)

        checksum = self._generate_checksum(main_payload)

        # ====================================================
        # HEALTH
        # ====================================================

        total_agents = len(self._summary_extractors)

        health = PipelineHealth(
            total_agents=total_agents,
            successful_agents=successful_agents,
            failed_agents=failed_agents,
            success_rate=round(
                successful_agents / total_agents * 100,
                2
            )
            if total_agents
            else 0.0,
        )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        payload = FinalPayload(
            status="completed",
            artifacts_present=artifacts_status,
            payload=main_payload,
            checksum=checksum,
        )

        result = ResultContract(
            version=self.CONTRACT_VERSION,
            timestamp=datetime.now(
                timezone.utc
            ).isoformat(),
            execution_id=ctx.get("execution_id"),
            final_result=asdict(payload),
            summary=final_summary,
            next_steps=sorted(dynamic_next_steps),
            health=asdict(health),
        )

        logger.info(
            "[RESULT_AGENT] Contract generated successfully"
        )

        return asdict(result)

    # ========================================================
    # PAYLOAD RESOLUTION
    # ========================================================

    def _resolve_main_payload(
        self,
        ctx: Dict[str, Any]
    ) -> Any:

        priority_order = [
            "ast_validator",
            "validator",
            "critic",
            "style_validator",
            "multi_coder",
            "coder",
            "backend_builder",
            "frontend_builder",
            "api_builder",
        ]

        for node in priority_order:

            data = ctx.get(node)

            if not data:
                continue

            if isinstance(data, dict):

                artifact = data.get("output")

                if artifact:

                    code = getattr(artifact, "code", None)

                    if code:
                        return code

                    files = getattr(artifact, "files", None)

                    if files:
                        return files

        return (
            ctx.get("final_output")
            or ctx.get("generated_file")
            or {}
        )

    # ========================================================
    # CHECKSUM
    # ========================================================

    def _generate_checksum(
        self,
        payload: Any
    ) -> str:

        try:

            serialized = str(payload).encode()

            return hashlib.sha256(
                serialized
            ).hexdigest()

        except Exception:

            return "checksum_error"

    # ========================================================
    # EXTRACTORS
    # ========================================================

    def _extract_docs_summary(
        self,
        data: Any
    ) -> Tuple[Optional[str], List[str]]:

        if isinstance(data, dict):

            if data.get("readme"):
                return (
                    "Technical documentation generated",
                    []
                )

        return (
            "Documentation available",
            ["Review generated documentation"]
        )

    def _extract_release_summary(
        self,
        data: Any
    ) -> Tuple[Optional[str], List[str]]:

        if not isinstance(data, dict):
            return None, []

        changelog = data.get("changelog")

        if changelog:

            return (
                f"Release notes generated ({str(changelog)[:80]}...)",
                ["Validate release notes"]
            )

        return (
            "Release metadata processed",
            []
        )

    def _extract_metrics_summary(
        self,
        data: Any
    ) -> Tuple[Optional[str], List[str]]:

        if not isinstance(data, dict):
            return None, []

        durations = data.get(
            "durations",
            {}
        )

        quality = data.get(
            "quality_scores",
            {}
        )

        metrics = []

        if durations:

            total_time = sum(
                float(v)
                for v in durations.values()
            )

            metrics.append(
                f"Execution Time: {total_time:.2f}s"
            )

        if quality:

            avg_quality = (
                sum(quality.values())
                / len(quality)
            )

            metrics.append(
                f"Quality: {avg_quality:.2f}/10"
            )

        return (
            " | ".join(metrics),
            []
        )

    def _extract_optimization_summary(
        self,
        data: Any
    ) -> Tuple[Optional[str], List[str]]:

        if not isinstance(data, dict):
            return None, []

        patterns = data.get(
            "patterns",
            []
        )

        if patterns:

            return (
                f"{len(patterns)} optimization opportunities detected",
                [
                    "Apply recommended CPU optimizations",
                    "Apply recommended memory optimizations",
                ]
            )

        return None, []

    def _extract_code_summary(
        self,
        data: Any
    ) -> Tuple[Optional[str], List[str]]:

        if not isinstance(data, dict):
            return None, []

        language = data.get(
            "language",
            "unknown"
        )

        tests = data.get(
            "tests_generated",
            False
        )

        return (
            f"Code artifact generated [{language}]",
            (
                []
                if tests
                else ["Generate unit tests"]
            )
        )

    def _extract_security_summary(
        self,
        data: Any
    ) -> Tuple[Optional[str], List[str]]:

        if not isinstance(data, dict):
            return None, []

        vulnerabilities = data.get(
            "vulnerabilities",
            []
        )

        criticals = [
            v
            for v in vulnerabilities
            if v.get("severity") == "critical"
        ]

        if criticals:

            return (
                f"Security Audit: {len(criticals)} critical vulnerabilities",
                [
                    "Immediate security remediation",
                    "Run SAST validation",
                    "Run DAST validation",
                ]
            )

        return (
            "Security audit passed",
            []
        )

    # ========================================================
    # EXTENSIBILITY API
    # ========================================================

    def register_extractor(
        self,
        agent_name: str,
        extractor: Callable[
            [Any],
            Tuple[Optional[str], List[str]]
        ]
    ) -> None:

        logger.info(
            "Registering extractor [%s]",
            agent_name
        )

        self._summary_extractors[
            agent_name
        ] = extractor
