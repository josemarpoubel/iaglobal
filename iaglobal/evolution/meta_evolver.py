# iaglobal/evolution/meta_evolver.py

import json
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from iaglobal._paths import META_EVOLUTION_FILE
from iaglobal.cognition.learning.classifier_memory import ClassifierMemory
from iaglobal.utils.logger import logger

META_CONFIG_FILE = META_EVOLUTION_FILE
MAX_TRIALS_WINDOW = (
    200  # Limite máximo de histórico para conter estouro de memória e lentidão de I/O
)


@dataclass
class EvolutionParams:
    mutation_rate: float = 0.1
    crossover_rate: float = 0.3
    selection_pressure: float = 0.8
    population_size: int = 6
    exploration_rate: float = 0.2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_rate": round(self.mutation_rate, 6),
            "crossover_rate": round(self.crossover_rate, 6),
            "selection_pressure": round(self.selection_pressure, 6),
            "population_size": self.population_size,
            "exploration_rate": round(self.exploration_rate, 6),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvolutionParams":
        return cls(
            mutation_rate=data.get("mutation_rate", 0.1),
            crossover_rate=data.get("crossover_rate", 0.3),
            selection_pressure=data.get("selection_pressure", 0.8),
            population_size=data.get("population_size", 6),
            exploration_rate=data.get("exploration_rate", 0.2),
        )


@dataclass
class MetaTrial:
    params: EvolutionParams
    improvement: float
    timestamp: float = field(default_factory=time.time)
    task_type: str = "general"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "params": self.params.to_dict(),
            "improvement": self.improvement,
            "timestamp": round(self.timestamp, 6),
            "task_type": self.task_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetaTrial":
        return cls(
            params=EvolutionParams.from_dict(data.get("params", {})),
            improvement=data.get("improvement", 0.0),
            timestamp=data.get("timestamp", time.time()),
            task_type=data.get("task_type", "general"),
        )


class MetaEvolver:
    """
    Evolui os parâmetros da evolução artificial com estabilidade concorrente.
    Controla taxas de mutação e exploração de forma dinâmica.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        classifier_memory: Optional[ClassifierMemory] = None,
    ):
        self.path = path or META_CONFIG_FILE
        self.classifier_memory = classifier_memory or ClassifierMemory()
        self.current_params = EvolutionParams()
        self.trials: List[MetaTrial] = []
        self._best_improvement = 0.0

        # 🔒 Lock atómico para mitigar condições de corrida concorrentes no disco e vetor de trials
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        with self._lock:
            try:
                if self.path.exists() and self.path.stat().st_size > 0:
                    with open(self.path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.current_params = EvolutionParams.from_dict(
                            data.get("current_params", {})
                        )

                        raw_trials = data.get("trials", [])
                        # Garante a importação cortando o excesso se o arquivo antigo estivesse inflado
                        self.trials = [
                            MetaTrial.from_dict(t)
                            for t in raw_trials[-MAX_TRIALS_WINDOW:]
                        ]

                        if self.trials:
                            self._best_improvement = max(
                                t.improvement for t in self.trials
                            )
            except json.JSONDecodeError:
                logger.error(
                    "[META] Arquivo meta_evolution.json corrompido. Inicializando novos parâmetros de fábrica."
                )
            except Exception as e:
                logger.debug("[META] Aviso ao carregar histórico meta-evolutivo: %s", e)

    def _save(self):
        # NOTA DE DESIGN: Sempre invocado sob o contexto seguro do self._lock externo
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "current_params": self.current_params.to_dict(),
                "trials": [t.to_dict() for t in self.trials],
            }
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(
                "[META-CRITICAL] Falha catastrófica ao persistir metadados evolutivos: %s",
                e,
            )

    def record_trial(
        self, params: EvolutionParams, improvement: float, task_type: str = "general"
    ):
        """Regista o resultado de um ciclo de evolução, aplicando a janela deslizante de RAM/Disk."""
        with self._lock:
            trial = MetaTrial(
                params=params, improvement=improvement, task_type=task_type
            )
            self.trials.append(trial)

            if improvement > self._best_improvement:
                self._best_improvement = improvement

            # ✂️ Janela Deslizante (Sliding Window): Mantém apenas as amostras mais recentes e relevantes
            if len(self.trials) > MAX_TRIALS_WINDOW:
                self.trials = self.trials[-MAX_TRIALS_WINDOW:]

            self.adapt_params(improvement)
            self._save()

    def adapt_params(self, last_improvement: float):
        """Aplica a heurística reativa de adaptação contínua (Exploration vs Exploitation)."""
        if not self.trials:
            return

        avg_improvement = sum(t.improvement for t in self.trials) / len(self.trials)

        if avg_improvement < 5.0:
            # Sistema estagnado: Reduz mutação e expande crossover para recombinar genes consolidados
            self.current_params.mutation_rate = max(
                0.05, self.current_params.mutation_rate * 0.8
            )
            self.current_params.crossover_rate = min(
                0.5, self.current_params.crossover_rate * 1.2
            )
            logger.info(
                "[META] Convergência estagnada (Melhoria média: %.2f) — Ajustando crossover=%.3f mutation=%.3f",
                avg_improvement,
                self.current_params.crossover_rate,
                self.current_params.mutation_rate,
            )
        else:
            # Ótimo ritmo evolutivo: Minimiza taxas para consolidar o código estável gerado
            self.current_params.mutation_rate = max(
                0.05, self.current_params.mutation_rate * 0.7
            )
            self.current_params.exploration_rate = max(
                0.05, self.current_params.exploration_rate * 0.8
            )
            logger.info(
                "[META] Ritmo evolutivo saudável (Melhoria média: %.2f) — Consolidando: mutation=%.3f exploration=%.3f",
                avg_improvement,
                self.current_params.mutation_rate,
                self.current_params.exploration_rate,
            )

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            avg = (
                (sum(t.improvement for t in self.trials) / len(self.trials))
                if self.trials
                else 0.0
            )
            return {
                "current_params": self.current_params.to_dict(),
                "trials_count": len(self.trials),
                "best_improvement": self._best_improvement,
                "avg_improvement": avg,
                "classifier_bias": self.get_classifier_bias("general"),
            }

    def get_classifier_bias(self, task_type: str) -> float:
        try:
            return self.classifier_memory.get_bias(task_type)
        except Exception:
            return 0.0


# Singleton global para acesso simplificado
meta_evolver = MetaEvolver()
