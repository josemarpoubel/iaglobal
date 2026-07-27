# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ArtifactResolver — Contrato único de acesso a artefatos tipados no pipeline.

Centraliza a lógica de resolução de GeneratedArtifact para evitar duplicação
de heurísticas em dezenas de nós consumidores.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from iaglobal.core.artifact import GeneratedArtifact, ArtifactKind
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.graphs.artifact_resolver")


@dataclass
class ResolvedArtifact:
    """Resultado padronizado da resolução de artefato."""

    content: str
    kind: ArtifactKind
    source_node: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


def resolve_artifact(
    node_result: Any, source_name: str = "unknown"
) -> ResolvedArtifact:
    """
    Resolve um resultado de nó para ResolvedArtifact canônico.

    Ordem de prioridade:
    1. GeneratedArtifact explícito (em NodeResult.artifacts[0] ou dict["artifact"])
    2. GeneratedArtifact direto
    3. Fallback: node_result["output"] ou node_result["content"] + detecção via GeneratedArtifact.from_str
    4. Fallback final: string vazia + ArtifactKind.UNKNOWN
    """
    # Caso 0: NodeResult — usa contrato tipado diretamente
    if hasattr(node_result, "output") and hasattr(node_result, "success") and hasattr(node_result, "artifacts"):
        if node_result.artifacts and isinstance(node_result.artifacts[0], GeneratedArtifact):
            artifact = node_result.artifacts[0]
            _confidence = artifact.confidence if artifact.confidence > 0 else 1.0
            logger.debug(
                "[ARTIFACT_RESOLVER] %s: NodeResult.artifacts[0] (kind=%s)",
                source_name,
                artifact.kind,
            )
            return ResolvedArtifact(
                content=artifact.content,
                kind=artifact.kind,
                source_node=source_name,
                confidence=_confidence,
                metadata=artifact.metadata,
            )
        output = node_result.output or ""
        if output:
            gen_artifact = GeneratedArtifact.from_str(str(output))
            logger.debug(
                "[ARTIFACT_RESOLVER] %s: NodeResult.output via from_str (kind=%s)",
                source_name,
                gen_artifact.kind,
            )
            return ResolvedArtifact(
                content=str(output),
                kind=gen_artifact.kind,
                source_node=source_name,
                confidence=0.5,
                metadata={"fallback": True, "source_type": "node_result"},
            )

    # Caso 1: artefato explícito no dicionário
    if isinstance(node_result, dict):
        artifact = node_result.get("artifact")
        if isinstance(artifact, GeneratedArtifact):
            logger.debug(
                "[ARTIFACT_RESOLVER] %s: usando artifact explícito (kind=%s)",
                source_name,
                artifact.kind,
            )
            # Confidence alta pois temos artefato tipado explicitamente
            _confidence = artifact.confidence if artifact.confidence > 0 else 1.0
            return ResolvedArtifact(
                content=artifact.content,
                kind=artifact.kind,
                source_node=source_name,
                confidence=_confidence,
                metadata=artifact.metadata,
            )

        # Caso 2: o próprio resultado pode ser um GeneratedArtifact (embora raro em dict)
        # Caso 3: fallback para output/content/code/integrated_code
        output = (
            node_result.get("output")
            or node_result.get("content")
            or node_result.get("code")
            or node_result.get("integrated_code")
            or ""
        )
        if output:
            gen_artifact = GeneratedArtifact.from_str(str(output))
            logger.debug(
                "[ARTIFACT_RESOLVER] %s: fallback via from_str (kind=%s)",
                source_name,
                gen_artifact.kind,
            )
            return ResolvedArtifact(
                content=str(output),
                kind=gen_artifact.kind,
                source_node=source_name,
                confidence=0.5,
                metadata={"fallback": True, "original_keys": list(node_result.keys())},
            )

    # Caso 2: resultado direto é GeneratedArtifact
    if isinstance(node_result, GeneratedArtifact):
        logger.debug(
            "[ARTIFACT_RESOLVER] %s: resultado direto é GeneratedArtifact (kind=%s)",
            source_name,
            node_result.kind,
        )
        _confidence = node_result.confidence if node_result.confidence > 0 else 1.0
        return ResolvedArtifact(
            content=node_result.content,
            kind=node_result.kind,
            source_node=source_name,
            confidence=_confidence,
            metadata=node_result.metadata,
        )

    # Caso 3: string direta
    if isinstance(node_result, str) and node_result.strip():
        gen_artifact = GeneratedArtifact.from_str(node_result)
        logger.debug(
            "[ARTIFACT_RESOLVER] %s: string direta via from_str (kind=%s)",
            source_name,
            gen_artifact.kind,
        )
        return ResolvedArtifact(
            content=node_result,
            kind=gen_artifact.kind,
            source_node=source_name,
            confidence=0.3,
            metadata={"fallback": True, "type": "direct_string"},
        )

    # Caso 3b: string vazia ou whitespace-only
    if isinstance(node_result, str) and not node_result.strip():
        logger.debug("[ARTIFACT_RESOLVER] %s: string vazia detectada", source_name)
        return ResolvedArtifact(
            content="",
            kind=ArtifactKind.EMPTY,
            source_node=source_name,
            confidence=0.0,
            metadata={"fallback": True, "empty": True},
        )

    # Caso 4: objeto com atributo .code (ex: CodeArtifact, SolutionArtifact)
    if hasattr(node_result, "code") and getattr(node_result, "code", None):
        code = getattr(node_result, "code")
        gen_artifact = GeneratedArtifact.from_str(str(code))
        logger.debug(
            "[ARTIFACT_RESOLVER] %s: atributo .code via from_str (kind=%s)",
            source_name,
            gen_artifact.kind,
        )
        return ResolvedArtifact(
            content=str(code),
            kind=gen_artifact.kind,
            source_node=source_name,
            confidence=0.4,
            metadata={"fallback": True, "type": "code_attribute"},
        )

    # Caso 5: objeto com atributo .content
    if hasattr(node_result, "content") and getattr(node_result, "content", None):
        content = getattr(node_result, "content")
        gen_artifact = GeneratedArtifact.from_str(str(content))
        logger.debug(
            "[ARTIFACT_RESOLVER] %s: atributo .content via from_str (kind=%s)",
            source_name,
            gen_artifact.kind,
        )
        return ResolvedArtifact(
            content=str(content),
            kind=gen_artifact.kind,
            source_node=source_name,
            confidence=0.4,
            metadata={"fallback": True, "type": "content_attribute"},
        )

    # Fallback final
    logger.warning(
        "[ARTIFACT_RESOLVER] %s: nenhum conteúdo resolvível, retornando UNKNOWN",
        source_name,
    )
    return ResolvedArtifact(
        content="",
        kind=ArtifactKind.UNKNOWN,
        source_node=source_name,
        confidence=0.0,
        metadata={"fallback": True, "empty": True},
    )


def resolve_from_memory(memory: Dict[str, Any], source_name: str) -> ResolvedArtifact:
    """
    Resolve artefato a partir do dicionário de memória do pipeline.

    Uso padrão nos nós:
        artifact = resolve_from_memory(ctx.get("memory", {}), "coder")
        code = artifact.content
        kind = artifact.kind
    """
    node_result = memory.get(source_name, {})
    return resolve_artifact(node_result, source_name)


def get_best_artifact(
    memory: Dict[str, Any], preferred_sources: Tuple[str, ...] = None
) -> ResolvedArtifact:
    """
    Busca o melhor artefato disponível na memória, tentando fontes em ordem de preferência.

    Args:
        memory: Dicionário de memória do pipeline (ctx["memory"])
        preferred_sources: Ordem de preferência das fontes (padrão: fontes de geração de código)

    Returns:
        ResolvedArtifact do primeiro fonte com conteúdo válido
    """
    if preferred_sources is None:
        preferred_sources = (
            "multi_coder",
            "coder",
            "debug_coder",
            "backend_builder",
            "frontend_builder",
            "api_builder",
            "database_builder",
            "code_executor",
            "integrator",
        )

    for source in preferred_sources:
        if source in memory:
            artifact = resolve_from_memory(memory, source)
            if artifact.content:
                return artifact

    # Nenhuma fonte com conteúdo
    return ResolvedArtifact(
        content="",
        kind=ArtifactKind.EMPTY,
        source_node="none",
        confidence=0.0,
    )
