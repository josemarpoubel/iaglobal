# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
TokenBucket — Rate limiter adaptativo com priorização por IVM.

Protege o modelo local (qwen2.5:0.5b) contra thrashing de CPU em
hardware limitado (4 núcleos, sem GPU). Substitui o Semaphore fixo
por um sistema de cadência dinâmica:

  - Burst quando ocioso (até N tokens acumulados)
  - Cadência estrita sob carga (rate controlado por latência)
  - Priorização: agentes de baixo IVM são rejeitados sob pressão
  - Circuit breaker: latência > 1000ms → só agentes críticos passam

ETAPA 4 (ROADMAP_2): LocalModelGate com buckets independentes por tier
cognitivo (JUIZ/glm4=2, OPERARIO/qwen=6, SENTINELA/lfm=8). Integra com
TaskRouter para classificar node_id → tier e publica sinalização de
congestão no AcetylcholineBus para degradação adaptativa proativa.
"""

import asyncio
import time
from typing import ClassVar, Dict, Optional

from iaglobal.utils.logger import get_logger
from iaglobal.metabolism.bucket_manager import TokenBucket

logger = get_logger("iaglobal.token_bucket")


class LocalModelGate:
    """Portão adaptativo para acesso ao modelo local com buckets por tier.

    Implementa o Etapa 4 do ROADMAP_2: buckets independentes por tier
    cognitivo (GLM4=2, Qwen=6, LFM=8). Integra com TaskRouter para classificar
    node_id → tier e publica sinalização de congestão no AcetylcholineBus para
    degradação adaptativa proativa.

    Mapeia node_id para tier baseado no mapeamento semântico:
    - Prefixo "no_critic*" / "critic" → tier "glm4" (Juiz)
    - Prefixo "no_coder*" / "coder" / o padrão geral → tier "qwen" (Operário)
    - Prefixo "no_sentinel*" / "sentinel" → tier "lfm" (Sentinela)

    Evento de congestão: se as rejeições do bucket > 70%, publica
    't congestion' com métricas por tier (utilization_, rejections_) no
    barramento, permitindo ao PipelineEngine reduzir a complexidade por
    tier automaticamente.
    """

    _instance: ClassVar["LocalModelGate | None"] = None
    _instance_lock = asyncio.Lock()

    # Mapa base de prioridade — node_id → score 0.0-1.0
    _PRIORITY_MAP: ClassVar[dict[str, float]] = {
        "critic": 0.95,
        "planner": 0.75,
        "architect": 0.72,
        "coder": 0.65,
        "debugger": 0.60,
        "tester": 0.55,
        "validator": 0.50,
        "search": 0.50,
        "pm": 0.50,
        "dependency": 0.45,
        "security": 0.45,
        "enhancement": 0.45,
        "reflexion": 0.60,
        "orchestrator": 0.70,
        "result": 0.40,
        "retrospective": 0.35,
        "scheduler": 0.30,
        "skill": 0.30,
        "evolution": 0.65,
    }

    # Capacidades por tier do ROADMAP_2
    BUCKET_CAPACITY: ClassVar[dict[str, int]] = {
        "glm4": 2,  # Juiz: processamento crítico, 1 por vez
        "qwen": 6,  # Operário: fluxo principal, throughput moderado
        "lfm": 8,  # Sentinela: monitor+validation rápido, paralelismo máximo
    }

    def __init__(self) -> None:
        # Importar TaskRouter para classificação de node_id → tier
        from iaglobal.providers.task_router import TaskRouter

        self.router = TaskRouter()

        # Buckets independentes por tier
        self.buckets: Dict[str, TokenBucket] = {}
        for tier in self.BUCKET_CAPACITY:
            self.buckets[tier] = TokenBucket(
                capacity=self.BUCKET_CAPACITY[tier],
                fill_rate=self.BUCKET_CAPACITY[tier] / 60.0,  # 1 tok/s
                max_concurrent=self.BUCKET_CAPACITY[tier],
            )

        # Métricas de operação por tier
        self._rejected_counts: Dict[str, int] = {"glm4": 0, "qwen": 0, "lfm": 0}
        self._alerts_fired: Dict[str, int] = {"glm4": 0, "qwen": 0, "lfm": 0}
        self._event: asyncio.Event = asyncio.Event()

    @classmethod
    async def get_instance(cls) -> "LocalModelGate":
        async with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    @classmethod
    async def reset_instance(cls) -> "LocalModelGate":
        async with cls._instance_lock:
            cls._instance = cls()
        return cls._instance

    def _get_tier_from_node(self, node_id: str) -> str:
        """Mapeia node_id para tier cognitivo usando TaskRouter."""
        return self.router.get_role_for_node(node_id)

    @classmethod
    def get_priority(cls, node_id: str) -> float:
        """Mapeia node_id para prioridade 0.0-1.0 para o tier correspondente."""
        nid = (
            (node_id or "")
            .lower()
            .replace("_agent", "")
            .replace("agent_", "")
            .replace("no_", "")
        )
        for key, prio in cls._PRIORITY_MAP.items():
            if key in nid:
                return prio
        return 0.35  # default baixo — fail-safe

    async def release(self, node_id: str) -> None:
        """Libera slot no bucket do tier do node_id."""
        tier = self._get_tier_from_node(node_id)
        bucket = self.buckets.get(tier)
        if bucket:
            await bucket.release()

    async def try_acquire(self, node_id: str) -> bool:
        """Tenta adquirir um slot no bucket do tier do node_id.

        Retorna True se adquirido, False se deve usar synthetic_success (fallback).
        Se rejeição por tier > 70%, dispara um sinal de “altamente congestionado”.
        """
        tier = self._get_tier_from_node(node_id)
        bucket = self.buckets.get(tier)
        if not bucket:
            # Em caso de tier desconhecido, assume fall back (sem aquisição)
            return False

        # priority retido para uso futuro (circuit breaker por tier);
        # o BucketManager.TokenBucket controla concorrência por capacidade.
        _ = self.get_priority(node_id)
        acquired = await bucket.acquire(
            estimated_tokens=1,
            timeout=0.5,  # timeout curto — proxy para queue sem bloqueio
        )

        # Registrar rejeição para métricas
        if not acquired:
            self._rejected_counts[tier] = self._rejected_counts.get(tier, 0) + 1
            # Alerta > 70% de rejeições (filtrado por bateria)
            if self._rejected_counts[tier] >= self.BUCKET_CAPACITY[tier] * 0.7:
                await self._fire_tier_congestion_alert(tier, bucket)
        else:
            # Resetar contador de rejeições em cada sucesso (por bateria)
            self._rejected_counts[tier] = 0

        return acquired

    async def _fire_tier_congestion_alert(self, tier: str, bucket: TokenBucket) -> None:
        """Dispara sinal de congestão no barramento se ainda não disparado.

        Anexa o estado da fila (current_concurrency) para que o
        JOLMetricsCollector calcule a tendência de exaustão antes do
        threshold de rejeição ser atingido.
        """
        if self._alerts_fired.get(tier, 0) >= 1:
            return
        self._alerts_fired[tier] = 1

        try:
            from iaglobal.graphs.comms.acetylcholine_bus import AgentMessage, bus

            payload = {
                "tier": tier,
                "status": "highly_congested",
                "usage_pct": round(bucket.utilization * 100, 1),
                "rejections": self._rejected_counts[tier],
                "capacity": bucket.capacity,
                "current_concurrency": bucket.current_concurrent,
                "fill_rate": round(bucket.fill_rate, 2),
                "timestamp": time.time(),
            }
            msg = AgentMessage(
                sender="local_model_gate",
                recipient="pipeline_engine",
                message_type="tier_congestion_alert",
                content=payload,
            )
            await bus.publish(msg)
            logger.info(
                "[LOCAL_GATE] Congestion alert -> tier=%s usage=%.1f%% "
                "conc=%d/%d rejections=%d",
                tier,
                payload["usage_pct"],
                payload["current_concurrency"],
                payload["capacity"],
                payload["rejections"],
            )
        except Exception as e:
            logger.debug("[LOCAL_GATE] Falha ao publicar congestão: %s", e)

    def get_metrics(self) -> Dict:
        """Retorna métricas operacionais por tier para coleta JOL.

        Integração directa com `metabolism/bucket_manager.py`'s TokenBucket.
        """
        return {
            tier: {
                "tokens": bucket.tokens,
                "capacity": bucket.capacity,
                "utilization_pct": round(bucket.utilization * 100, 1),
                "rejections": self._rejected_counts[tier],
                "max_concurrent": bucket.max_concurrent,
            }
            for tier, bucket in self.buckets.items()
        }

    def report_latency(self, latency_ms: float) -> None:
        """Registra latência média por tier para circuit breaker adaptativo por tier.

        Ajusta dinamicamente fill_rate do bucket (capacidade por segundo)
        baseado no backlog acumulativo. Versão síncrona para chamada no
        finally block de BanditPolicy (não em corrotina).
        """
        # Rate-limita atualizações para evitar spam
        if not hasattr(self, "_last_latency_report"):
            self._last_latency_report = time.monotonic()
        now = time.monotonic()
        if now - self._last_latency_report < 10:
            return
        self._last_latency_report = now

        for tier, bucket in self.buckets.items():
            # Define floor mínimo por tier
            _floors = {"glm4": 0.5, "qwen": 1.0, "lfm": 0.5}
            floor = _floors.get(tier, 0.3)

            # Rastreia reduções consecutivas para evitar estrangulamento
            if not hasattr(self, "_consecutive_reductions"):
                self._consecutive_reductions: dict[str, int] = {}
            cons = self._consecutive_reductions.get(tier, 0)

            # Só reduz se latência > 5s (antes 800ms) e ainda não estabilizou
            if latency_ms > 5000 and cons < 3:
                bucket.fill_rate = max(floor, bucket.fill_rate - 0.2)
                self._consecutive_reductions[tier] = cons + 1
                logger.warning(
                    "[LOCAL_GATE] Tier %s fill_rate reduzido para %.1f tok/s (latency=%.0fms, reduction=%d/3)",
                    tier,
                    bucket.fill_rate,
                    latency_ms,
                    cons + 1,
                )
            elif latency_ms < 300:
                # Recupera fill_rate em baixa carga
                bucket.fill_rate = min(10.0, bucket.fill_rate + 1.0)

    @property
    def is_degraded(self) -> bool:
        """True se qualquer tier está altamente congestionado.

        Lógica de degradação: se qualquer tier tem > 70% rejeições, o sistema todo
        é considerado degradado para acionamento proativo no pipeline.
        """
        for tier, count in self._rejected_counts.items():
            if count >= self.BUCKET_CAPACITY[tier] * 0.7:
                return True
        return False

    async def waiter_deferred_reduction(
        self, tier: str, reduction: float = 0.3
    ) -> None:
        """Reduz fill_rate de um tier em resposta a um alerta (único por tier).

        Chamado pelo PipelineEngine quando recebe um alert de tier_congestion_alert.
        Permite redução gradual em vez de AIYM abrupta.
        """
        bucket = self.buckets.get(tier)
        if not bucket:
            return
        old = bucket.fill_rate
        bucket.fill_rate = max(0.1, bucket.fill_rate * (1.0 - reduction))
        if old != bucket.fill_rate:
            logger.info(
                "[LOCAL_GATE] Tier %s fill_rate reduzido %.1f→%.1f tok/s (redução de %.0f%%)",
                tier,
                old,
                bucket.fill_rate,
                reduction * 100,
            )
