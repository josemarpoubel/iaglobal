#!/usr/bin/env python3
"""
MetaLearner — Geração 3: Aprendizado de Alto Nível

O Meta-Learner não executa tarefas — ele:
1. Analisa padrões de falha/sucesso em nível arquitetural
2. Sugere melhorias automáticas no pipeline
3. Auto-ajusta configurações (epsilon, thresholds, weights)
4. Realiza reflexão pós-execução
5. Gera backlog evolutivo baseado em dados
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from statistics import mean

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.meta")


@dataclass
class ExecutionPattern:
    """Padrão de execução detectado."""

    pattern_id: str
    task_type: str
    success: bool
    avg_latency_ms: float
    avg_ivm: float
    provider_used: str
    config_used: Dict
    occurrence_count: int = 1
    first_seen: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_seen: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ArchitecturalSuggestion:
    """Sugestão de melhoria arquitetural."""

    suggestion_id: str
    category: str
    priority: str
    description: str
    current_state: Dict
    suggested_state: Dict
    expected_improvement: str
    confidence: float
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class EvolutionBacklogItem:
    """Item do backlog de evolução."""

    item_id: str
    item_type: str
    description: str
    rationale: str
    priority_score: float
    estimated_impact: str
    status: str = "backlog"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class MetaLearner:
    """Sistema de meta-aprendizado arquitetural."""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path("iaglobal/memory/meta_learner.json")
        self.success_patterns: Dict[str, ExecutionPattern] = {}
        self.failure_patterns: Dict[str, ExecutionPattern] = {}
        self.suggestions: Dict[str, ArchitecturalSuggestion] = {}
        self.evolution_backlog: Dict[str, EvolutionBacklogItem] = {}
        self.auto_tuned_configs: Dict[str, float] = {
            "bandit_epsilon": 0.1,
            "bandit_decay": 0.99,
            "mitosis_threshold": 0.75,
            "alert_threshold": 0.3,
        }
        self.execution_history: List[Dict] = []
        self._load_state()
        logger.info("🧠 [META] Meta-Learner initialized")

    async def analyze_execution(
        self,
        task_type: str,
        success: bool,
        metrics: Dict[str, Any],
        config: Dict[str, Any],
        provider: str = "unknown",
        ivm: float = 0.5,
    ):
        """Analisa uma execução e identifica padrões."""
        execution_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_type": task_type,
            "success": success,
            "metrics": metrics,
            "config": config,
            "provider": provider,
            "ivm": ivm,
        }
        self.execution_history.append(execution_record)

        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-1000:]

        pattern_key = f"{task_type}_{success}_{provider}"
        pattern = self._find_or_create_pattern(
            pattern_key, task_type, success, metrics, config, provider, ivm
        )

        if success:
            self.success_patterns[pattern_key] = pattern
        else:
            self.failure_patterns[pattern_key] = pattern

        await self._analyze_for_insights(task_type, success, metrics, config, ivm)
        self._auto_tune_configs()
        await self._save_state()

        logger.debug(
            f"🧠 [META] Execução analisada: {task_type} {'✅' if success else '❌'}"
        )

    def _find_or_create_pattern(
        self,
        pattern_key: str,
        task_type: str,
        success: bool,
        metrics: Dict,
        config: Dict,
        provider: str,
        ivm: float,
    ) -> ExecutionPattern:
        """Encontra ou cria padrão de execução."""
        existing = self.success_patterns.get(pattern_key) or self.failure_patterns.get(
            pattern_key
        )

        if existing:
            existing.occurrence_count += 1
            existing.last_seen = datetime.now(timezone.utc).isoformat()
            existing.avg_latency_ms = (
                existing.avg_latency_ms * (existing.occurrence_count - 1)
                + metrics.get("latency_ms", 0)
            ) / existing.occurrence_count
            existing.avg_ivm = (
                existing.avg_ivm * (existing.occurrence_count - 1) + ivm
            ) / existing.occurrence_count
            return existing
        else:
            return ExecutionPattern(
                pattern_id=pattern_key,
                task_type=task_type,
                success=success,
                avg_latency_ms=metrics.get("latency_ms", 0),
                avg_ivm=ivm,
                provider_used=provider,
                config_used=config,
                occurrence_count=1,
            )

    async def _analyze_for_insights(
        self, task_type: str, success: bool, metrics: Dict, config: Dict, ivm: float
    ):
        """Analisa execução em busca de insights."""
        if not success:
            failure_count = sum(
                p.occurrence_count
                for k, p in self.failure_patterns.items()
                if task_type in k
            )
            if failure_count >= 5:
                await self._generate_suggestion(
                    category="reliability",
                    priority="high" if failure_count >= 10 else "medium",
                    description=f"Falhas recorrentes em {task_type} ({failure_count} ocorrências)",
                    current_state={
                        "task_type": task_type,
                        "failure_count": failure_count,
                    },
                    suggested_state={"action": "investigate_root_cause"},
                    expected_improvement="Redução de falhas em 50%+",
                    confidence=min(0.9, failure_count / 20),
                )

        latency = metrics.get("latency_ms", 0)
        if latency > 5000 and ivm < 0.5:
            await self._generate_suggestion(
                category="performance",
                priority="medium",
                description=f"Alta latência ({latency:.0f}ms) com baixo IVM ({ivm:.3f})",
                current_state={"latency_ms": latency, "ivm": ivm},
                suggested_state={"optimize_pipeline": True, "consider_caching": True},
                expected_improvement="Redução de latência em 30-50%",
                confidence=0.7,
            )

    async def _generate_suggestion(
        self,
        category: str,
        priority: str,
        description: str,
        current_state: Dict,
        suggested_state: Dict,
        expected_improvement: str,
        confidence: float,
    ):
        """Gera sugestão arquitetural."""
        suggestion_id = f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        suggestion = ArchitecturalSuggestion(
            suggestion_id=suggestion_id,
            category=category,
            priority=priority,
            description=description,
            current_state=current_state,
            suggested_state=suggested_state,
            expected_improvement=expected_improvement,
            confidence=confidence,
        )
        self.suggestions[suggestion_id] = suggestion
        logger.info(
            f"🧠 [META] Nova sugestão: {suggestion_id} ({category}, {priority})"
        )

        await self._add_to_backlog(
            item_type="optimization" if category == "performance" else "fix",
            description=description,
            rationale=f"Sugestão auto-gerada com {confidence:.1%} de confiança",
            priority_score=confidence,
            estimated_impact=expected_improvement,
        )

    async def _add_to_backlog(
        self,
        item_type: str,
        description: str,
        rationale: str,
        priority_score: float,
        estimated_impact: str,
    ):
        """Adiciona item ao backlog evolutivo."""
        item_id = f"{item_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        item = EvolutionBacklogItem(
            item_id=item_id,
            item_type=item_type,
            description=description,
            rationale=rationale,
            priority_score=priority_score,
            estimated_impact=estimated_impact,
        )
        self.evolution_backlog[item_id] = item
        logger.debug(f"📋 [META] Backlog item criado: {item_id}")

    def _auto_tune_configs(self):
        """Auto-ajusta configurações baseado em padrões."""
        if len(self.execution_history) < 50:
            return

        recent = self.execution_history[-50:]
        success_rate = sum(1 for e in recent if e["success"]) / len(recent)
        avg_ivm = mean(e["ivm"] for e in recent) if recent else 0.5

        if success_rate < 0.7:
            self.auto_tuned_configs["bandit_epsilon"] = min(
                0.3, self.auto_tuned_configs["bandit_epsilon"] + 0.02
            )
            logger.info(
                f"🎛️ [META] Aumentando epsilon para {self.auto_tuned_configs['bandit_epsilon']:.3f}"
            )
        elif success_rate > 0.9 and avg_ivm > 0.8:
            self.auto_tuned_configs["bandit_epsilon"] = max(
                0.05, self.auto_tuned_configs["bandit_epsilon"] - 0.01
            )
            logger.info(
                f"🎛️ [META] Reduzindo epsilon para {self.auto_tuned_configs['bandit_epsilon']:.3f}"
            )

        if avg_ivm > 0.85:
            self.auto_tuned_configs["mitosis_threshold"] = max(
                0.6, self.auto_tuned_configs["mitosis_threshold"] - 0.05
            )

    def get_suggestions(
        self, category: Optional[str] = None, min_confidence: float = 0.5
    ) -> List[ArchitecturalSuggestion]:
        """Retorna sugestões filtradas."""
        suggestions = list(self.suggestions.values())
        if category:
            suggestions = [s for s in suggestions if s.category == category]
        suggestions = [s for s in suggestions if s.confidence >= min_confidence]
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        suggestions.sort(
            key=lambda s: (priority_order.get(s.priority, 3), -s.confidence)
        )
        return suggestions

    def get_backlog(
        self, priority_min: float = 0.5, status: str = "backlog"
    ) -> List[EvolutionBacklogItem]:
        """Retorna backlog evolutivo priorizado."""
        items = [
            i
            for i in self.evolution_backlog.values()
            if i.priority_score >= priority_min and i.status == status
        ]
        items.sort(key=lambda i: i.priority_score, reverse=True)
        return items

    def get_auto_tuned_config(self, key: str) -> Optional[float]:
        """Retorna configuração auto-ajustada."""
        return self.auto_tuned_configs.get(key)

    async def _save_state(self):
        """Persiste estado em disco."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "success_patterns": {
                k: asdict(v) for k, v in self.success_patterns.items()
            },
            "failure_patterns": {
                k: asdict(v) for k, v in self.failure_patterns.items()
            },
            "suggestions": {k: asdict(v) for k, v in self.suggestions.items()},
            "evolution_backlog": {
                k: asdict(v) for k, v in self.evolution_backlog.items()
            },
            "auto_tuned_configs": self.auto_tuned_configs,
            "execution_history": self.execution_history[-100:],
        }
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

    def _load_state(self):
        """Carrega estado de disco."""
        if not self.db_path.exists():
            return
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            for k, v in state.get("success_patterns", {}).items():
                self.success_patterns[k] = ExecutionPattern(**v)
            for k, v in state.get("failure_patterns", {}).items():
                self.failure_patterns[k] = ExecutionPattern(**v)
            for k, v in state.get("suggestions", {}).items():
                self.suggestions[k] = ArchitecturalSuggestion(**v)
            for k, v in state.get("evolution_backlog", {}).items():
                self.evolution_backlog[k] = EvolutionBacklogItem(**v)
            self.auto_tuned_configs.update(state.get("auto_tuned_configs", {}))
            self.execution_history = state.get("execution_history", [])
            logger.info(f"🧠 [META] Estado carregado")
        except Exception as e:
            logger.error(f"🧠 [META] Erro ao carregar estado: {e}")


# Singleton
_meta_learner_instance: Optional[MetaLearner] = None


def get_meta_learner() -> MetaLearner:
    """Retorna singleton do MetaLearner."""
    global _meta_learner_instance
    if _meta_learner_instance is None:
        _meta_learner_instance = MetaLearner()
    return _meta_learner_instance
