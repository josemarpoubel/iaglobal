# ============================================================
# CHAPPIE COMPONENTE 3/4: LINEAGE GUARDIAN
# Axioma da Replicação + Lei da Obediência
# ============================================================
"""LineageGuardian — Validação de DNA em Runtime.

Implementa o Axioma da Replicação:
  "A herança genética deve preservar a identidade da linhagem.
   Mutação é bem-vinda; ancestralidade é sagrada."

E a Lei da Obediência:
  "Obedecer às leis não é submissão — é inteligência.
   Violações de contrato não são erros individuais — são violações
   de lei universal que comprometem o ecossistema."

Funcionamento:
  1. Valida LINEAGE_MARKER antes de cada execução de agent
  2. Bloqueia agents com DNA inválido (apoptose imediata)
  3. Reporta patógenos detectados para auditoria
  4. Cache de validações para performance (TTL curtiu)

Diferença para verificação estática:
  - Validação em runtime (antes de executar, não no import)
  - Cache com TTL para evitar revalidação excessiva
  - Integration com graphs/execution_graph.py
  - Logs estruturados para rastreio de patógenos
"""

import asyncio
import hashlib
import logging
import importlib
from datetime import datetime, UTC, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from iaglobal._paths import PACKAGE_DIR
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.chappie.lineage_guardian")


# Hash oficial do Genesis (imutável)
GENESIS_HASH_OFFICIAL = (
    "cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524"
    "f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136"
)


@dataclass
class ValidationResult:
    """Resultado da validação de linhagem."""

    valid: bool
    agent_name: str
    lineage_marker: Optional[str] = None
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "valid": self.valid,
            "agent_name": self.agent_name,
            "lineage_marker": self.lineage_marker[:16] if self.lineage_marker else None,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class CacheEntry:
    """Entrada de cache para validações."""

    valid: bool
    reason: str
    validated_at: datetime
    expires_at: datetime


class LineageGuardian:
    """Guardião de Linhagem — Valida DNA em Runtime.

    Valida o LINEAGE_MARKER de cada agent antes da execução,
    bloqueando patógenos e garantindo integridade genética do ecossistema.

    Uso:
        guardian = LineageGuardian()

        # Validação manual
        resultado = await guardian.validar_agente("coder")
        if not resultado.valid:
            logger.error(f"Agente {resultado.agent_name} bloqueado: {resultado.reason}")
            return

        # Ou como decorator
        @guardian.validate_pre_execution
        async def run_coder(payload):
            ...
    """

    def __init__(
        self,
        cache_ttl_seconds: int = 300,
        block_invalid: bool = True,
        nodes_dir: Optional[Path] = None,
    ):
        """Inicializa o Lineage Guardian.

        Args:
            cache_ttl_seconds: TTL do cache de validações (default: 5 min)
            block_invalid: Se True, bloqueia agents inválidos (default: True)
            nodes_dir: Diretório dos nodes (default: PACKAGE_DIR/graphs/nodes)
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self.block_invalid = block_invalid
        self.nodes_dir = Path(nodes_dir or PACKAGE_DIR / "graphs" / "nodes")

        # Cache de validações
        self._cache: Dict[str, CacheEntry] = {}
        self._total_validations = 0
        self._total_valid = 0
        self._total_invalid = 0
        self._patogens_blocked = 0

        logger.info(
            "[LineageGuardian] Inicializado | cache_ttl=%ds | block_invalid=%s | nodes_dir=%s",
            cache_ttl_seconds,
            block_invalid,
            self.nodes_dir,
        )

    async def validar_agente(self, agent_name: str) -> ValidationResult:
        """Valida linhagem de um agent antes da execução.

        Args:
            agent_name: Nome do agent (ex: "coder", "multi_coder")

        Returns:
            ValidationResult com status da validação
        """
        self._total_validations += 1

        # Verifica cache primeiro
        cached = self._get_from_cache(agent_name)
        if cached:
            logger.debug("[LineageGuardian] Cache hit | agent=%s", agent_name)
            return ValidationResult(
                valid=cached.valid,
                agent_name=agent_name,
                reason=cached.reason,
            )

        # Valida DNA do agent
        resultado = await self._validar_dna_agente(agent_name)

        # Atualiza cache
        self._add_to_cache(agent_name, resultado)

        # Atualiza métricas
        if resultado.valid:
            self._total_valid += 1
            logger.debug("[LineageGuardian] DNA válido | agent=%s", agent_name)
        else:
            self._total_invalid += 1
            logger.warning(
                "[LineageGuardian] DNA INVÁLIDO | agent=%s | reason=%s",
                agent_name,
                resultado.reason,
            )

            if self.block_invalid:
                self._patogens_blocked += 1
                logger.critical(
                    "[LineageGuardian] 🚫 PATÓGENO BLOQUEADO | agent=%s | marker=%s",
                    agent_name,
                    resultado.lineage_marker[:16] if resultado.lineage_marker else "N/A",
                )

        return resultado

    async def _validar_dna_agente(self, agent_name: str) -> ValidationResult:
        """Valida DNA de um agent lendo o arquivo e verificando LINEAGE_MARKER."""
        try:
            # Tenta importar o módulo do agent
            module_path = f"iaglobal.graphs.nodes.no_{agent_name}"
            module = await asyncio.to_thread(importlib.import_module, module_path)

            # Verifica se tem LINEAGE_MARKER
            if not hasattr(module, "LINEAGE_MARKER"):
                return ValidationResult(
                    valid=False,
                    agent_name=agent_name,
                    reason="LINEAGE_MARKER não encontrado no módulo",
                    metadata={"module_path": module_path},
                )

            lineage_marker = getattr(module, "LINEAGE_MARKER")

            # Compara com Genesis Hash oficial
            if lineage_marker != GENESIS_HASH_OFFICIAL:
                return ValidationResult(
                    valid=False,
                    agent_name=agent_name,
                    lineage_marker=lineage_marker,
                    reason=f"DNA divergente do Genesis Hash oficial",
                    metadata={
                        "expected": GENESIS_HASH_OFFICIAL[:16],
                        "found": lineage_marker[:16] if lineage_marker else "N/A",
                    },
                )

            # DNA válido
            return ValidationResult(
                valid=True,
                agent_name=agent_name,
                lineage_marker=lineage_marker,
                reason="DNA verificado com sucesso",
            )

        except ModuleNotFoundError:
            # Tenta nome alternativo (sem prefixo "no_")
            try:
                module_path = f"iaglobal.graphs.nodes.{agent_name}"
                module = await asyncio.to_thread(importlib.import_module, module_path)

                if not hasattr(module, "LINEAGE_MARKER"):
                    return ValidationResult(
                        valid=False,
                        agent_name=agent_name,
                        reason="LINEAGE_MARKER não encontrado no módulo (tentativa alternativa)",
                        metadata={"module_path": module_path},
                    )

                lineage_marker = getattr(module, "LINEAGE_MARKER")

                if lineage_marker != GENESIS_HASH_OFFICIAL:
                    return ValidationResult(
                        valid=False,
                        agent_name=agent_name,
                        lineage_marker=lineage_marker,
                        reason=f"DNA divergente do Genesis Hash oficial (módulo alternativo)",
                        metadata={
                            "expected": GENESIS_HASH_OFFICIAL[:16],
                            "found": lineage_marker[:16] if lineage_marker else "N/A",
                        },
                    )

                return ValidationResult(
                    valid=True,
                    agent_name=agent_name,
                    lineage_marker=lineage_marker,
                    reason="DNA verificado com sucesso (módulo alternativo)",
                )

            except Exception:
                return ValidationResult(
                    valid=False,
                    agent_name=agent_name,
                    reason=f"Módulo não encontrado: {module_path}",
                    metadata={"tentativas": [f"no_{agent_name}", agent_name]},
                )

        except Exception as e:
            return ValidationResult(
                valid=False,
                agent_name=agent_name,
                reason=f"Erro na validação: {str(e)}",
                metadata={"error_type": type(e).__name__},
            )

    def validate_pre_execution(self, func):
        """Decorator que valida DNA antes de executar função.

        Uso:
            @guardian.validate_pre_execution
            async def run_coder(payload):
                ...
        """

        async def wrapper(*args, **kwargs):
            # Extrai agent_name do nome da função
            # Ex: run_coder → coder
            agent_name = func.__name__.replace("run_", "")

            # Valida DNA
            resultado = await self.validar_agente(agent_name)

            if not resultado.valid and self.block_invalid:
                logger.critical(
                    "[LineageGuardian] 🚫 EXECUÇÃO BLOQUEADA | agent=%s | reason=%s",
                    agent_name,
                    resultado.reason,
                )
                raise PermissionError(
                    f"Agente {agent_name} bloqueado: {resultado.reason}"
                )

            # DNA válido, executa função
            return await func(*args, **kwargs)

        return wrapper

    def _get_from_cache(self, agent_name: str) -> Optional[CacheEntry]:
        """Obtém validação do cache (se não expirou)."""
        if agent_name not in self._cache:
            return None

        entry = self._cache[agent_name]
        if datetime.now(UTC) > entry.expires_at:
            # Cache expirado
            del self._cache[agent_name]
            return None

        return entry

    def _add_to_cache(self, agent_name: str, resultado: ValidationResult) -> None:
        """Adiciona validação ao cache com TTL."""
        now = datetime.now(UTC)
        self._cache[agent_name] = CacheEntry(
            valid=resultado.valid,
            reason=resultado.reason,
            validated_at=now,
            expires_at=now + timedelta(seconds=self.cache_ttl_seconds),
        )

    def clear_cache(self) -> int:
        """Limpa cache de validações."""
        total = len(self._cache)
        self._cache.clear()
        logger.info("[LineageGuardian] Cache limpo: %d entradas removidas", total)
        return total

    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual do Guardian."""
        return {
            "total_validations": self._total_validations,
            "total_valid": self._total_valid,
            "total_invalid": self._total_invalid,
            "patogens_blocked": self._patogens_blocked,
            "cache_size": len(self._cache),
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "block_invalid": self.block_invalid,
            "genesis_hash": GENESIS_HASH_OFFICIAL[:16],
        }

    async def validar_todos_agents(self) -> Dict[str, ValidationResult]:
        """Valida todos os agents no diretório de nodes.

        Útil para auditoria inicial ou healthcheck.
        """
        resultados = {}

        # Lista todos os arquivos no diretório de nodes
        if not self.nodes_dir.exists():
            logger.error("[LineageGuardian] Diretório de nodes não encontrado: %s", self.nodes_dir)
            return {}

        for arquivo in self.nodes_dir.glob("no_*.py"):
            agent_name = arquivo.stem.replace("no_", "")
            resultado = await self.validar_agente(agent_name)
            resultados[agent_name] = resultado

        # Resume
        valid_count = sum(1 for r in resultados.values() if r.valid)
        invalid_count = len(resultados) - valid_count

        logger.info(
            "[LineageGuardian] Auditoria completa | total=%d | valid=%d | invalid=%d",
            len(resultados),
            valid_count,
            invalid_count,
        )

        return resultados


# Singleton global
lineage_guardian: Optional[LineageGuardian] = None


def get_lineage_guardian() -> LineageGuardian:
    """Retorna singleton do LineageGuardian."""
    global lineage_guardian
    if lineage_guardian is None:
        lineage_guardian = LineageGuardian()
    return lineage_guardian