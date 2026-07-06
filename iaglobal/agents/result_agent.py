# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/result_agent.py

from __future__ import annotations

import hashlib
import json
import asyncio
import logging

from dataclasses import dataclass, asdict

from datetime import datetime, timezone

from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from iaglobal.agents.agent_base import AgentBase
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

class ResultAgent(AgentBase):
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
        super().__init__(agent_name="result")
        self._summary_extractors = {}
        self._register_default_extractors()

    def _register_default_extractors(self):
        self.register_extractor("documentation", self._extract_docs_summary)
        self.register_extractor("release", self._extract_release_summary)
        self.register_extractor("metrics", self._extract_metrics_summary)
        self.register_extractor("optimization", self._extract_optimization_summary)
        self.register_extractor("coder", self._extract_code_summary)
        self.register_extractor("security_audit", self._extract_security_summary)
        self.register_extractor("planner", self._extract_generic_summary)
        self.register_extractor("search", self._extract_generic_summary)
        self.register_extractor("review", self._extract_generic_summary)
        self.register_extractor("multi_coder", self._extract_code_summary)
        self.register_extractor("critic", self._extract_generic_summary)
        self.register_extractor("validator", self._extract_generic_summary)
        self.register_extractor("ast_validator", self._extract_generic_summary)
        self.register_extractor("security", self._extract_security_summary)

    async def _call_summary_extractor(self, agent_name: str, data: Any) -> Tuple[Optional[str], List[str]]:
        extractor = self._summary_extractors.get(agent_name)
        if extractor:
            if asyncio.iscoroutinefunction(extractor):
                return await extractor(data)
            return extractor(data)
        return self._extract_generic_summary(data)

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

    async def _persist_contract(self, result: dict) -> Path:
        from iaglobal._paths import RESULTS_DIR
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        path = RESULTS_DIR / f"contract_{ts}.json"

        def _mkdir_and_write():
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            return path

        return await asyncio.to_thread(_mkdir_and_write)

    # ========================================================
    # PUBLIC API
    # ========================================================

    async def build_result(
        self,
        ctx: Dict[str, Any]
    ) -> Dict[str, Any]:

        logger.info(
            "[RESULT_AGENT] Building Final Execution Contract..."
        )

        # 🧬 REFLEXÃO GENÔMICA (The Great Loop)
        # O ResultAgent analisa a execução e propõe mutações para o Bandit
        await self._reflect_on_execution(ctx)

        summary_parts: List[str] = []

        artifacts_status: Dict[str, bool] = {}

        dynamic_next_steps: Set[str] = set()

        successful_agents = 0
        failed_agents = 0

        # ====================================================
        # SAFE EXTRACTION LOOP
        # ====================================================

        for agent_name in self._summary_extractors:

            agent_data = ctx.get(agent_name)

            has_data = bool(agent_data)

            artifacts_status[agent_name] = has_data

            if not has_data:
                failed_agents += 1
                continue

            try:

                summary, next_steps = await self._call_summary_extractor(agent_name, agent_data)

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

        contract = asdict(result)
        try:
            await self._persist_contract(contract)
        except Exception as e:
            logger.warning("[RESULT_AGENT] Failed to persist contract: %s", e)
        return contract

    # ========================================================
    # GENOMIC REFLECTION (The Great Loop)
    # ========================================================

    async def _reflect_on_execution(self, ctx: Dict[str, Any]) -> None:
        """
        Analisa a performance da execução e sugere mutações para a BanditPolicy.
        Isso fecha o loop: Resultado -> Aprendizado -> Ajuste de DNA.
        """
        try:
            from iaglobal.graphs.bandit import _get_bandit
            bandit = _get_bandit()
            
            execution_id = ctx.get("execution_id", "unknown")
            
            # Analisamos quais modelos foram usados e seu sucesso
            # Se um modelo foi excelente, sugerimos aumentar seu peso (exploit)
            # Se foi redundante (EntropySentinel), sugerimos penalidade
            
            for node, data in ctx.items():
                if isinstance(data, dict) and "model" in data:
                    model = data["model"]
                    success = data.get("success", True)
                    latency = data.get("latency", 0.0)
                    
                    # Proposta de mutação baseada no resultado real
                    if success and latency < 2.0:
                        # Modelo altamente eficiente -> Reforço positivo
                        bandit.update_policy(node, model, "default", True, latency, 1.0)
                    elif not success:
                        # Falha -> Penalidade
                        bandit.update_policy(node, model, "default", False, latency, 0.0)
            
            logger.info("[RESULT_AGENT] 🧬 Reflexão Genômica concluída para exec=%s", execution_id)
        except Exception as e:
            logger.error("[RESULT_AGENT] Falha na Reflexão Genômica: %s", e)

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

                    if isinstance(artifact, str):
                        return artifact

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

    async def _extract_docs_summary(
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

    async def _extract_release_summary(
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

    async def _extract_metrics_summary(
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

    async def _extract_optimization_summary(
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

    async def _extract_code_summary(
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

    async def _extract_security_summary(
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
