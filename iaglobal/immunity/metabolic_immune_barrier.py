# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Barreira imunológica do telemetry/cache (Metabolic Immune Barrier).

Elimina a "degradação silenciosa" do metabolismo LLM: antes, respostas
vazias/obsoletas servidas do cache eram reportadas como `success=True`
sem nunca chegar ao provider, e o `system_analysis` agregava `alerta=False`
porque esses eventos não chegavam a nenhum sensor.

A barreira registra eventos imunológicos de integridade metabólica:
  - cache_poison      : entrada tóxica (vazia/curta) encontrada -> apoptosada
  - stale_cache       : entrada expirada por TTL -> apoptosada
  - synthetic_success : sucesso declarado sem geração real (ex: fallback de
                        select_model engolido por except)
  - import_failure    : falha de import de nó silenciada pelo proxy dinâmico

Quando qualquer evento de integridade ocorre, `is_degraded()` vira True e o
`no_system_analysis` o reflete em `alerta`, cumprindo a Lei 1 (a célula sente
seu próprio estado).
"""
from typing import Dict, List, Optional, Tuple

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.immunity.metabolic_barrier")

_DEGRADATION_KINDS = ("cache_poison", "stale_cache", "synthetic_success", "import_failure")
_ALL_KINDS = _DEGRADATION_KINDS + ("cache_valid_hit",)


class _MetabolicImmuneBarrier:
    """Singleton da barreira imunológica do telemetry/cache."""

    def __init__(self) -> None:
        self._counts: Dict[str, int] = {k: 0 for k in _ALL_KINDS}
        self._recent: List[Tuple[str, Optional[str], Optional[str]]] = []
        self._degraded: bool = False

    def record(self, kind: str, detail: Optional[str] = None, agent: Optional[str] = None) -> None:
        """Registra um evento imunológico. Eventos de degradação ativam a flag."""
        if kind not in self._counts:
            kind = "synthetic_success"
        self._counts[kind] += 1
        if kind in _DEGRADATION_KINDS:
            self._degraded = True
        self._recent.append((kind, detail, agent))
        if len(self._recent) > 50:
            self._recent.pop(0)
        if kind in _DEGRADATION_KINDS:
            logger.warning(
                "[BARRIER] evento imunológico=%s | detail=%s | agent=%s",
                kind, detail, agent,
            )
        else:
            logger.info(
                "[BARRIER] evento imunológico=%s | detail=%s | agent=%s",
                kind, detail, agent,
            )

    def is_degraded(self) -> bool:
        """True se qualquer evento de integridade metabólica ocorreu na sessão."""
        return self._degraded

    def counts(self) -> Dict[str, int]:
        return dict(self._counts)

    def recent(self, limit: int = 10) -> List[Tuple[str, Optional[str], Optional[str]]]:
        return list(self._recent[-limit:])

    def reset(self) -> None:
        """Limpa o estado da barreira (usado por testes e por apoptose de sessão)."""
        self._counts = {k: 0 for k in _ALL_KINDS}
        self._recent = []
        self._degraded = False


barrier = _MetabolicImmuneBarrier()
