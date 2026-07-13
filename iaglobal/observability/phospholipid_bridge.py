# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
PhospholipidBanditBridge — ponte entre BanditPolicy e PhospholipidRegistry.

Fornece instance-level load balancing com adaptive decay para o BanditPolicy.
Usado como hook em BanditPolicy.generate() para monitorar saúde de provedores.

Fluxo:
  1. BanditPolicy seleciona modelo (ε-greedy)
  2. Bridge.query(provider) → verifica registry
  3. Se há instâncias → load balancer seleciona a mais saudável
  4. Executa chamada → reporta health (latency, success/error)
  5. Se falha → adaptive decay + fallback
"""

import time
from typing import Any, Optional

from iaglobal.observability.registry import (
    ServiceInstance,
    registry as default_registry,
)
from iaglobal.observability.load_balancer import PhospholipidLoadBalancer
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.observability.phospholipid_bridge")


class PhospholipidBanditBridge:
    """Bridge entre BanditPolicy e PhospholipidRegistry para LB de instâncias."""

    def __init__(
        self,
        registry: Any = None,
        load_balancer: Any = None,
    ):
        self.registry = registry or default_registry
        if load_balancer is not None:
            self.load_balancer = load_balancer
        else:
            self.load_balancer = PhospholipidLoadBalancer(registry=self.registry)

    def provider_from_model(self, model_name: str) -> str:
        """Extrai provider do nome do modelo (ex: 'groq/llama3-70b' → 'groq')."""
        return model_name.split("/")[0] if "/" in model_name else model_name

    def has_registered_services(self, provider: str) -> bool:
        self.registry.check_timeouts()
        return any(
            s.name.startswith(provider) for s in self.registry._services.values()
        )

    async def select_instance(self, provider: str) -> Optional[ServiceInstance]:
        """Seleciona a instância mais saudável para um provider."""
        return await self.load_balancer.select(service_type=provider)

    def report_success(self, service_name: str, latency_ms: float = 0.0):
        """Reporta sucesso ao registry e load balancer."""
        self.load_balancer.report_success(service_name)
        self.registry.report_health(service_name, latency_ms=latency_ms, error=False)
        logger.info(
            "[PHOSPHOLIPID_BRIDGE] Sucesso reportado: %s (latency=%.1fms)",
            service_name,
            latency_ms,
        )

    def report_failure(self, service_name: str, error: Exception):
        """Reporta falha com adaptive decay."""
        instance = self.registry.get(service_name)
        if instance:
            self.load_balancer._handle_failure(instance, error)
        else:
            logger.warning(
                "[PHOSPHOLIPID_BRIDGE] Instância não encontrada para reportar falha: %s",
                service_name,
            )

    async def execute_with_health(
        self,
        model_name: str,
        prompt: str,
        task_type: str = "general",
        node_id: str = "provider_router",
        timeout: float = 30.0,
    ) -> str:
        """Executa modelo com health monitoring via registry.

        Se o provider tem instâncias registradas:
          - Seleciona a mais saudável
          - Monitora latência e sucesso/falha
          - Aplica adaptive decay em caso de falha
          - Fallback para instância alternativa ou default

        Se não há instâncias registradas:
          - Executa normalmente sem monitoring
        """
        from iaglobal.providers.provider_router import async_route_generate

        provider = self.provider_from_model(model_name)
        start = time.time()

        if self.has_registered_services(provider):
            instance = await self.select_instance(provider)

            if instance:
                logger.info(
                    "[PHOSPHOLIPID_BRIDGE] %s → instância %s (peso=%.2f, health=%s)",
                    model_name,
                    instance.name,
                    instance.weight,
                    instance.health,
                )
                try:
                    result = await async_route_generate(
                        model=model_name,
                        prompt=prompt,
                        task_type=task_type,
                        node_id=node_id,
                    )
                    latency_ms = (time.time() - start) * 1000
                    success = bool(result and str(result).strip())

                    if success:
                        self.report_success(instance.name, latency_ms)
                        return str(result)

                    self.report_failure(
                        instance.name,
                        RuntimeError(f"Resposta vazia para {model_name}"),
                    )
                except Exception as e:
                    latency_ms = (time.time() - start) * 1000
                    self.report_failure(instance.name, e)
                    logger.warning(
                        "[PHOSPHOLIPID_BRIDGE] Falha em %s, tentando fallback...",
                        instance.name,
                    )

                instance2 = await self.select_instance(provider)
                if instance2 and instance2.name != instance.name:
                    logger.info(
                        "[PHOSPHOLIPID_BRIDGE] Fallback para %s",
                        instance2.name,
                    )
                    try:
                        result = await async_route_generate(
                            model=model_name,
                            prompt=prompt,
                            task_type=task_type,
                            node_id=node_id,
                        )
                        if result and str(result).strip():
                            latency_ms = (time.time() - start) * 1000
                            self.report_success(instance2.name, latency_ms)
                            return str(result)
                    except Exception as e2:
                        self.report_failure(instance2.name, e2)

                logger.warning(
                    "[PHOSPHOLIPID_BRIDGE] Todas as instâncias de %s falharam",
                    provider,
                )

        return ""

    def auto_report(self, model_name: str, success: bool, latency_ms: float):
        """Auto-report metrics ao registry baseado no resultado da execução.

        Chamado do finally block do BanditPolicy.generate().
        Encontra serviços registrados que correspondem ao provider e
        atualiza suas métricas de saúde.
        """
        provider = self.provider_from_model(model_name)
        if not self.has_registered_services(provider):
            return
        for svc in list(self.registry._services.values()):
            if svc.name.startswith(provider):
                self.registry.report_health(
                    svc.name, latency_ms=latency_ms, error=not success
                )

    def register_provider_instance(
        self,
        name: str,
        endpoint: str,
        weight: float = 1.0,
        capacity: int = 10,
    ) -> ServiceInstance:
        """Registra uma instância de provedor no PhospholipidRegistry.

        Exemplo:
          bridge.register_provider_instance("groq-api", "https://api.groq.com/openai/v1")
          bridge.register_provider_instance("ollama-local", "http://localhost:11434")
        """
        return self.registry.register(name, endpoint, weight=weight, capacity=capacity)


bridge = PhospholipidBanditBridge()
