# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
EvolutionFeedbackHook — alimenta semaphore_health no Bandit.

Após cada execução, lê as métricas de contenção dos semáforos e
aplica ajustes nos pesos do Bandit para priorizar modelos saudáveis.

Lógica de ajuste:
  - timeout_rate > 0.3 → penalidade de -0.2 no peso do modelo
  - avg_wait_ms > 2000 → penalidade de -0.1
  - gate_rejections > 5  → penalidade de -0.1
  - leak_ratio > 0.01    → penalidade de -0.3 (provável leak)

Persistência:
  Cada ajuste é registrado em memória (`feedback_history`) e em disco
  (JSONL em iaglobal/memory/data/evolution/bandit_feedback.jsonl).
"""

from __future__ import annotations

import enum
import json
import time as _time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal")


@dataclass
class EvolutionSignal:
    """Sinal unificado de feedback evolutivo para um nó/provedor.

    Agrega métricas de múltiplas fontes (semáforos, métricas de execução,
    qualidade da geração, resultado do QA) em um único objeto transitável.
    """

    provider: str = ""
    model: str = ""
    semaphore_health: Optional[Dict[str, Dict[str, float]]] = None
    execution_metrics: Optional[Dict[str, Any]] = None
    generation_kind: Optional[str] = None  # GenerationKind.value
    qa_result: Optional[Dict[str, Any]] = None


class EvolutionFeedbackHook:
    """
    Hook pós-execução: ajusta pesos do Bandit com base na
    saúde dos semáforos.

    Uso:
        hook = EvolutionFeedbackHook()
        await hook.apply(bandit, semaphore_health)
    """

    TIMEOUT_RATE_THRESHOLD = 0.3
    WAIT_MS_THRESHOLD = 2000.0
    GATE_REJECTION_THRESHOLD = 5
    LEAK_RATIO_THRESHOLD = 0.01

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        self._feedback_log: list[dict[str, Any]] = []
        if persist_path is None:
            try:
                from iaglobal._paths import PACKAGE_DIR

                persist_path = (
                    PACKAGE_DIR.parent
                    / "memory"
                    / "data"
                    / "evolution"
                    / "bandit_feedback.jsonl"
                )
            except Exception:
                persist_path = Path("/tmp/iaglobal_bandit_feedback.jsonl")
        self._persist_path = persist_path
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_history()

    def _load_history(self) -> None:
        """Recupera ajustes anteriores do disco."""
        if not self._persist_path.exists():
            return
        try:
            with open(self._persist_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._feedback_log.append(json.loads(line))
            if self._feedback_log:
                logger.info(
                    "[FEEDBACK] Carregados %d ajustes do histórico em %s",
                    len(self._feedback_log),
                    self._persist_path,
                )
        except Exception as exc:
            logger.debug("[FEEDBACK] Falha ao carregar histórico: %s", exc)

    def _append_persist(self, entry: dict[str, Any]) -> None:
        """Append de um ajuste no arquivo JSONL."""
        try:
            with open(self._persist_path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug("[FEEDBACK] Falha ao persistir ajuste: %s", exc)

    async def apply(
        self,
        bandit: Any,
        signal: Optional[EvolutionSignal] = None,
        execution_id: str = "",
    ) -> None:
        """
        Aplica feedback multivetorial nos pesos do Bandit.

        Agrega sinais de semáforos, métricas de execução, qualidade da geração
        e resultado do QA em um único objeto ``EvolutionSignal`` antes de
        calcular penalidades e atualizar pesos.

        Args:
            bandit: instância de BanditPolicy
            signal: EvolutionSignal com os sinais de feedback do ciclo
        """
        if signal is None:
            return

        if isinstance(signal, dict):
            signal = EvolutionSignal(
                provider=signal.get("provider", ""),
                model=signal.get("model", ""),
                semaphore_health=signal.get("semaphore_health"),
                execution_metrics=signal.get("execution_metrics"),
                generation_kind=signal.get("generation_kind"),
                qa_result=signal.get("qa_result"),
            )

        model_key = self._resolve_model_key(bandit, signal.model)
        if model_key is None:
            return

        semaphore_p, semaphore_r = self._apply_semaphore_penalty(signal)
        generation_p, generation_r = self._apply_generation_penalty(signal)
        qa_p, qa_r = self._apply_qa_penalty(signal)

        penalty = semaphore_p + generation_p + qa_p
        reasons = semaphore_r + generation_r + qa_r

        if penalty != 0.0:
            current = bandit.weights.get(model_key, 0.0)
            new_weight = max(-2.0, current + penalty)
            bandit.weights[model_key] = new_weight
            entry = {
                "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S", _time.gmtime()),
                "execution_id": execution_id,
                "model": signal.model,
                "provider": signal.provider,
                "model_key": model_key,
                "generation_kind": signal.generation_kind,
                "qa_approved": (
                    signal.qa_result.get("approved")
                    if isinstance(signal.qa_result, dict)
                    else None
                ),
                "penalty": round(penalty, 3),
                "weight_before": round(current, 3),
                "weight_after": round(new_weight, 3),
                "reasons": reasons,
            }
            self._append_persist(entry)
            self._feedback_log.append(entry)
            logger.debug(
                "[FEEDBACK] %s: %.3f → %.3f (%s)",
                model_key,
                current,
                new_weight,
                "; ".join(reasons),
            )

    def _apply_semaphore_penalty(
        self, signal: EvolutionSignal
    ) -> tuple[float, list[str]]:
        metrics = (signal.semaphore_health or {}).get(signal.model, {})
        penalty = 0.0
        reasons: list[str] = []
        timeout_rate = metrics.get("timeout_rate", 0.0)
        if timeout_rate > self.TIMEOUT_RATE_THRESHOLD:
            p = round(min(timeout_rate, 1.0) * 0.4, 3)
            penalty -= p
            reasons.append(f"timeout_rate={timeout_rate:.2f} penalty={p:.3f}")

        avg_wait_ms = metrics.get("avg_wait_ms", 0.0)
        if avg_wait_ms > self.WAIT_MS_THRESHOLD:
            ratio = min(avg_wait_ms / 10000.0, 1.0)
            p = round(ratio * 0.2, 3)
            penalty -= p
            reasons.append(f"avg_wait={avg_wait_ms:.0f}ms penalty={p:.3f}")

        gate_rejections = metrics.get("gate_rejections", 0)
        if gate_rejections > self.GATE_REJECTION_THRESHOLD:
            p = round(min(gate_rejections / 20.0, 1.0) * 0.15, 3)
            penalty -= p
            reasons.append(f"gate_rejections={gate_rejections} penalty={p:.3f}")

        leak_ratio = metrics.get("leak_ratio", 0.0)
        if leak_ratio > self.LEAK_RATIO_THRESHOLD:
            penalty -= 0.3
            reasons.append(f"leak_ratio={leak_ratio:.4f} penalty=0.300")

        return penalty, reasons

    @staticmethod
    def _generation_penalty(kind: Optional[str]) -> tuple[float, list[str]]:
        if kind is None:
            return 0.0, []
        penalties: dict[str, tuple[float, str]] = {
            "error_page": (0.25, "generation=ERROR_PAGE"),
            "html": (0.20, "generation=HTML"),
            "empty": (0.15, "generation=EMPTY"),
            "unknown": (0.05, "generation=UNKNOWN"),
            "code": (0.0, "generation=CODE"),
            "markdown": (0.0, "generation=MARKDOWN"),
        }
        p, label = penalties.get(kind, (0.0, f"generation={kind}"))
        if p:
            return -p, [f"{label} penalty={p:.2f}"]
        return 0.0, []

    def _apply_generation_penalty(
        self,
        signal: EvolutionSignal,
    ) -> tuple[float, list[str]]:
        return self._generation_penalty(signal.generation_kind)

    def _apply_qa_penalty(
        self,
        signal: EvolutionSignal,
    ) -> tuple[float, list[str]]:
        qa = signal.qa_result
        if not isinstance(qa, dict):
            return 0.0, []
        approved = qa.get("approved")
        structured = qa.get("structured")
        if approved is False:
            return -0.20, ["qa_rejected penalty=0.20"]
        if structured is False and qa.get("error") == "critic_missing_verdict":
            return -0.05, ["critic_missing_verdict penalty=0.05"]
        if structured is False:
            return -0.10, ["qa_unstructured penalty=0.10"]
        return 0.0, []

    def _resolve_model_key(self, bandit: Any, model_name: str) -> Optional[str]:
        """Encontra a chave do modelo no dict `weights` do Bandit."""
        for key in bandit.weights:
            if model_name in key:
                return key
        return None

    @property
    def feedback_history(self) -> list[dict[str, Any]]:
        return list(self._feedback_log)


__all__ = ["EvolutionFeedbackHook", "EvolutionSignal"]
